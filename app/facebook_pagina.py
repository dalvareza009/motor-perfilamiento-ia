"""Personas que interactúan con una página de Facebook (reacciones, comentarios y shares).

La página (por ejemplo MAPFRE) se lee con la sesión de Chrome. De cada
publicación se sacan quienes reaccionaron (positivas y negativas), comentaron o
compartieron, el enlace a su perfil y, si Facebook lo muestra, ficha y contacto.
El comentario acotado queda en la ficha de la persona.
"""
import re
import unicodedata
from urllib.parse import parse_qs, unquote, urlparse

from app.database import get_connection
from app.gustos import acercamiento_de_gusto, clasificar, producto_de_gusto

TOPE_PERSONAS = 50
TOPE_PUBLICACIONES = 10
PAGINA_DEFECTO = "https://www.facebook.com/Mapfreco"

_RESERVADAS = {
    "watch", "groups", "events", "login", "marketplace", "gaming", "reels", "stories",
    "bookmark", "friends", "memories", "saved", "ads", "privacy", "policies", "help",
    "settings", "notifications", "search", "share", "photos", "photo.php", "videos",
    "permalink.php", "story.php", "hashtag", "pages", "posts", "reel", "video",
    "photo", "live", "fundraisers", "composer", "dialog", "recover", "reg",
    "checkpoint", "home.php", "index.php", "messages", "messaging", "sharer",
    "share.php", "story.php", "watch", "reel", "stories", "people", "profile.php",
}

_RUIDO_NOMBRE = {
    "me gusta", "comentar", "compartir", "like", "comment", "share", "facebook",
    "seguir", "follow", "ver más", "ver mas", "see more", "responder", "reply",
    "todas las reacciones", "all reactions",
}

DDL = """
CREATE TABLE IF NOT EXISTS public.interactuantes_pagina (
    id SERIAL PRIMARY KEY,
    pagina_url TEXT NOT NULL,
    pagina_nombre TEXT,
    persona_url TEXT NOT NULL,
    nombre TEXT NOT NULL,
    likes INTEGER NOT NULL DEFAULT 0,
    comentarios INTEGER NOT NULL DEFAULT 0,
    compartidos INTEGER NOT NULL DEFAULT 0,
    textos TEXT NOT NULL DEFAULT '',
    publicaciones TEXT NOT NULL DEFAULT '',
    ficha TEXT NOT NULL DEFAULT '',
    contacto TEXT NOT NULL DEFAULT '',
    acercamiento TEXT NOT NULL DEFAULT '',
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS interactuantes_pagina_pagina_persona
    ON public.interactuantes_pagina (pagina_url, persona_url);
ALTER TABLE public.interactuantes_pagina ADD COLUMN IF NOT EXISTS compartidos INTEGER NOT NULL DEFAULT 0;
ALTER TABLE public.interactuantes_pagina ADD COLUMN IF NOT EXISTS reacciones_pos INTEGER NOT NULL DEFAULT 0;
ALTER TABLE public.interactuantes_pagina ADD COLUMN IF NOT EXISTS reacciones_neg INTEGER NOT NULL DEFAULT 0;
ALTER TABLE public.interactuantes_pagina ADD COLUMN IF NOT EXISTS reacciones TEXT NOT NULL DEFAULT '';
CREATE TABLE IF NOT EXISTS public.paginas_seguros (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL DEFAULT '',
    fecha_alta TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.perfiles_recopilar (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    red TEXT NOT NULL DEFAULT '',
    nombre TEXT NOT NULL DEFAULT '',
    origen TEXT NOT NULL DEFAULT '',
    fecha_alta TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

_NEGATIVAS = ("enoj", "angry", "furioso", "entriste", "sad", "triste")
_POSITIVAS = ("gusta", "like", "encanta", "love", "importa", "care", "divierte",
              "haha", "jaja", "asombr", "wow")
_NOMBRE_REACCION = (
    ("enoj", "Me enoja"),
    ("angry", "Me enoja"),
    ("entriste", "Me entristece"),
    ("sad", "Me entristece"),
    ("encanta", "Me encanta"),
    ("love", "Me encanta"),
    ("importa", "Me importa"),
    ("care", "Me importa"),
    ("divierte", "Me divierte"),
    ("haha", "Me divierte"),
    ("jaja", "Me divierte"),
    ("asombr", "Me asombra"),
    ("wow", "Me asombra"),
    ("gusta", "Me gusta"),
    ("like", "Me gusta"),
)
_COMENTARIO_NEG = re.compile(
    r"estafa|horrible|pesimo|pésimo|odio|queja|reclamo|no sirve|mentira|"
    r"demora|no pagan|rabia|enoj|pésima|mala atencion|mala atención|"
    r"nunca mas|nunca más|no recomiendo|pésimo servicio", re.I)
_COMENTARIO_POS = re.compile(
    r"gracias|excelente|recomiendo|felicit|genial|me interesa|quiero saber|"
    r"información|informacion|muy bueno|me gusta|buen servicio|excelente atencion", re.I)


def _sin_tilde(texto):
    t = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


# En páginas de seguros de Colombia solo importan quienes viven o son de aquí.
_MARCA_COLOMBIA = (
    "colombia", "colombiano", "colombiana", "colombianos", "colombianas",
)
_LUGAR_COLOMBIA = (
    "bogota", "medellin", "cali", "barranquilla", "cartagena", "bucaramanga",
    "pereira", "manizales", "cucuta", "ibague", "villavicencio", "santa marta",
    "pasto", "armenia", "neiva", "sincelejo", "monteria", "valledupar", "tunja",
    "popayan", "riohacha", "chia", "soacha", "bello", "envigado", "itagui",
    "zipaquira", "sabaneta", "rionegro", "palmira", "soledad", "cajica",
    "mosquera", "funza", "fusagasuga", "girardot", "duitama", "sogamoso",
    "tulua", "giron", "floridablanca", "piedecuesta", "malambo", "cota",
    "facatativa", "yopal", "florencia", "quibdo", "arauca", "leticia",
    "san andres", "segovia", "remedios", "apartado", "turbo", "magangue",
    "dosquebradas", "itague", "antioquia", "cundinamarca", "atlantico",
    "bolivar", "valle del cauca", "santander", "norte de santander", "boyaca",
    "tolima", "huila", "narino", "cauca", "magdalena", "cesar", "cordoba",
    "sucre", "caldas", "risaralda", "quindio", "meta", "casanare", "choco",
    "caqueta", "putumayo", "guajira", "amazonas", "vichada", "vaupes",
    "guainia", "guaviare",
)
_EXTRANJERO = (
    "mexico", "espana", "spain", "argentina", "chile", "peru", "ecuador",
    "brasil", "brazil", "estados unidos", "united states", "miami", "orlando",
    "houston", "new york", "nueva york", "madrid", "barcelona", "cdmx",
    "ciudad de mexico", "lima", "santiago de chile", "buenos aires", "quito",
    "caracas", "panama", "costa rica", "guatemala", "honduras", "el salvador",
    "uruguay", "paraguay", "bolivia", "italia", "francia", "alemania",
    "canada", "australia", "inglaterra", "londres", "portugal",
)


def _texto_lugar(persona):
    if isinstance(persona, dict):
        partes = [persona.get("ubicacion"), persona.get("ficha"),
                  persona.get("acercamiento"), persona.get("contacto")]
        info = persona.get("info") if isinstance(persona.get("info"), dict) else {}
        partes.extend([info.get("ubicacion"), info.get("acerca")])
        textos = persona.get("textos") if isinstance(persona.get("textos"), list) else _partir(persona.get("textos"))
        partes.extend(textos or [])
        return " ".join(str(p or "") for p in partes)
    return str(persona or "")


def es_de_colombia(persona):
    """True si vive o es de Colombia, False si es claramente de otro país, None si no se sabe."""
    n = _sin_tilde(_texto_lugar(persona))
    if not n.strip():
        return None
    if any(m in n for m in _MARCA_COLOMBIA) or any(m in n for m in _LUGAR_COLOMBIA):
        return True
    if any(m in n for m in _EXTRANJERO):
        return False
    return None


def es_relevante_colombia(persona):
    """En páginas de seguros: se queda si es de Colombia o aún no hay ubicación."""
    return es_de_colombia(persona) is not False


def clasificar_reaccion(texto):
    """-> (positiva|negativa, nombre visible) según el tipo de reacción de Facebook."""
    n = _sin_tilde(texto)
    if any(k in n for k in _NEGATIVAS):
        return "negativa", _nombre_reaccion(n)
    if any(k in n for k in _POSITIVAS):
        return "positiva", _nombre_reaccion(n)
    return "positiva", "Me gusta"


def _nombre_reaccion(n):
    for clave, nombre in _NOMBRE_REACCION:
        if clave in n:
            return nombre
    return "Me gusta"


def tono_comentario(texto):
    """interés, desagrado o neutro a partir del texto del comentario."""
    t = str(texto or "")
    if _COMENTARIO_NEG.search(t):
        return "desagrado"
    if _COMENTARIO_POS.search(t):
        return "interés"
    return "neutro"


def _host(url):
    return (urlparse(url or "").hostname or "").lower().removeprefix("www.").removeprefix("m.")


def _partes(url):
    return [unquote(s) for s in urlparse(url or "").path.split("/") if s]


def claves_en_base(pagina_url=None):
    """Perfiles que ya están en la base: interactuantes y fichas de Facebook."""
    asegurar_tabla()
    conn = get_connection()
    claves = set()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT persona_url FROM public.interactuantes_pagina")
            claves.update(clave_perfil(r[0]) for r in cur.fetchall() if r and r[0])
            try:
                cur.execute("""SELECT DISTINCT fuente_url FROM public.hechos_perfil
                               WHERE LOWER(COALESCE(red, '')) LIKE %s""", ("%facebook%",))
                claves.update(clave_perfil(r[0]) for r in cur.fetchall() if r and r[0])
            except Exception:
                conn.rollback()
        return claves
    finally:
        conn.close()


def es_conocida(perfil, conocidas):
    return bool(perfil) and clave_perfil(perfil) in (conocidas or set())


def separar_nuevas(personas, conocidas):
    """Separa quienes aún no están en la base de quienes ya se trajeron."""
    nuevas, repetidas = [], []
    for p in personas or []:
        if es_conocida(p.get("perfil"), conocidas):
            repetidas.append(p)
        else:
            p = {**p, "nueva": True}
            nuevas.append(p)
    return nuevas, repetidas


def clave_perfil(url):
    """Id estable para comparar la página consigo misma o dos perfiles."""
    raw = (url or "").strip()
    if not raw:
        return ""
    partes = _partes(raw)
    bajas = [s.lower() for s in partes]
    if partes and bajas[0] == "profile.php":
        ids = parse_qs(urlparse(raw).query).get("id") or []
        return f"id:{ids[0]}" if ids else ""
    if partes and bajas[0] == "people" and len(partes) >= 3 and partes[-1].isdigit():
        return f"id:{partes[-1]}"
    if partes:
        return f"slug:{partes[0].lower()}"
    return raw.rstrip("/").lower()


def clasificar_url_pagina(url):
    """URL canónica de una página de Facebook, o None."""
    raw = (url or "").strip()
    if not raw.lower().startswith("https://"):
        return None
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    if host not in {"facebook.com", "fb.com"}:
        return None
    partes = [unquote(s) for s in parsed.path.split("/") if s]
    if not partes:
        return None
    bajas = [s.lower() for s in partes]
    if bajas[0] in {"login", "signin", "messages", "messaging", "groups", "watch",
                    "events", "marketplace", "reels", "stories", "search", "settings"}:
        return None
    if bajas[0] == "profile.php":
        ids = parse_qs(parsed.query).get("id") or []
        if ids and ids[0].isdigit():
            return f"https://www.facebook.com/profile.php?id={ids[0]}"
        return None
    if bajas[0] == "pages":
        utiles = [p for p in partes[1:] if p.lower() not in {"category"}]
        if utiles and utiles[-1].isdigit() and len(utiles) >= 2:
            return f"https://www.facebook.com/{utiles[0]}"
        if utiles:
            slug = utiles[-1] if not utiles[-1].isdigit() else utiles[0]
            return f"https://www.facebook.com/{slug}"
        return None
    slug = partes[0]
    if slug.lower() in _RESERVADAS or slug.lower().endswith(".php"):
        return None
    return f"https://www.facebook.com/{slug}"


def url_perfil_facebook(href, pagina_url=""):
    """Enlace de perfil usable, o None si es la página, un post, foto o ruido."""
    raw = (href or "").strip()
    if not raw:
        return None
    raw = raw.split("#")[0]
    if "l.php" in raw.lower():
        destino = (parse_qs(urlparse(raw).query).get("u") or [""])[0]
        raw = unquote(destino) if destino else raw
    if raw.startswith("/"):
        raw = "https://www.facebook.com" + raw
    if not raw.lower().startswith("http"):
        return None
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    if host not in {"facebook.com", "fb.com"}:
        return None
    partes = [unquote(s) for s in parsed.path.split("/") if s]
    if not partes:
        return None
    bajas = [s.lower() for s in partes]
    if bajas[0] == "profile.php":
        ids = parse_qs(parsed.query).get("id") or []
        if not (ids and ids[0].isdigit()):
            return None
        url = f"https://www.facebook.com/profile.php?id={ids[0]}"
        return None if clave_perfil(url) == clave_perfil(pagina_url) else url
    if bajas[0] == "people" and len(partes) >= 3 and re.fullmatch(r"\d+", partes[-1] or ""):
        url = f"https://www.facebook.com/profile.php?id={partes[-1]}"
        return None if clave_perfil(url) == clave_perfil(pagina_url) else url
    if bajas[0] in _RESERVADAS or bajas[0].endswith(".php"):
        return None
    if len(partes) >= 2 and bajas[1] in {"posts", "photos", "videos", "reels", "reel",
                                         "about", "friends", "followers", "following",
                                         "likes", "reviews", "live", "events", "videos"}:
        return None
    if len(partes) != 1:
        return None
    slug = partes[0]
    if slug.lower() in _RESERVADAS or slug.lower().endswith(".php"):
        return None
    url = f"https://www.facebook.com/{slug}"
    return None if clave_perfil(url) == clave_perfil(pagina_url) else url


def _nombre_ok(nombre):
    t = re.sub(r"\s+", " ", str(nombre or "")).strip()
    if not t or t.lower() in _RUIDO_NOMBRE:
        return ""
    if t.isdigit() or len(t) < 2:
        return ""
    return t[:120]


_TIEMPO_COMENTARIO = re.compile(
    r"^(hace\s+)?\d+\s*(min|h|d|sem|semana|mes|año|hr|hour|day|week|month|year)s?\b",
    re.I)


def _texto_es_el_nombre(texto, nombre):
    """True si Facebook nos dejó el autor, no la frase del comentario."""
    t = re.sub(r"\s+", " ", str(texto or "")).strip()
    n = _nombre_ok(nombre)
    if not t:
        return True
    if _TIEMPO_COMENTARIO.match(t) or t.lower() in _RUIDO_NOMBRE:
        return True
    if not n:
        return False
    a, b = _sin_tilde(t), _sin_tilde(n)
    return a == b or (b.startswith(a) and len(a) >= 4)


def _unir(valores, sep=" | "):
    vistos, partes = set(), []
    for v in valores or []:
        t = re.sub(r"\s+", " ", str(v or "")).strip()
        if t and t.lower() not in vistos:
            vistos.add(t.lower())
            partes.append(t[:4000])
    return sep.join(partes)


def _partir(texto):
    return [p.strip() for p in re.split(r"\s*\|\s*", str(texto or "")) if p.strip()]


def fusionar(personas, entrada):
    """Acumula like, comentario o share de la misma persona. Mutates `personas`."""
    perfil = url_perfil_facebook(entrada.get("perfil") or entrada.get("href") or "",
                                 entrada.get("pagina") or "")
    if not perfil:
        return personas
    nombre = _nombre_ok(entrada.get("nombre"))
    hallada = next((p for p in personas if p["perfil"] == perfil), None)
    if hallada is not None:
        hallada.setdefault("reacciones", [])
        hallada.setdefault("reacciones_pos", 0)
        hallada.setdefault("reacciones_neg", 0)
        if isinstance(hallada.get("reacciones"), str):
            hallada["reacciones"] = _partir(hallada["reacciones"])
    if hallada is None:
        hallada = {
            "nombre": nombre or perfil.rsplit("/", 1)[-1].replace(".", " "),
            "perfil": perfil,
            "likes": 0,
            "comentarios": 0,
            "compartidos": 0,
            "reacciones_pos": 0,
            "reacciones_neg": 0,
            "reacciones": [],
            "textos": [],
            "publicaciones": [],
        }
        personas.append(hallada)
    elif nombre:
        actual = hallada["nombre"] or ""
        slug = perfil.rsplit("/", 1)[-1].replace(".", " ").lower()
        if (not actual or actual.lower() == slug or "." in actual
                or (nombre[0].isupper() and actual and actual[0].islower())):
            hallada["nombre"] = nombre
    tipo = (entrada.get("tipo") or "").lower()
    reaccion = (entrada.get("reaccion") or "").strip()
    if tipo in {"negativa", "me enoja", "me entristece", "angry", "sad"}:
        hallada["reacciones_neg"] = int(hallada.get("reacciones_neg") or 0) + 1
        if reaccion:
            if reaccion not in hallada["reacciones"]:
                hallada["reacciones"].append(reaccion)
        elif "Me enoja" not in hallada["reacciones"]:
            hallada["reacciones"].append("Me enoja")
    elif tipo in {"like", "reaccion", "reacción", "me gusta", "positiva",
                  "me encanta", "me importa", "me divierte", "me asombra"}:
        hallada["likes"] += 1
        hallada["reacciones_pos"] = int(hallada.get("reacciones_pos") or 0) + 1
        nombre_r = reaccion or "Me gusta"
        if nombre_r not in hallada["reacciones"]:
            hallada["reacciones"].append(nombre_r)
    elif tipo in {"compartido", "compartida", "share", "shares"}:
        hallada["compartidos"] = int(hallada.get("compartidos") or 0) + 1
    elif tipo in {"comentario", "comment"}:
        hallada["comentarios"] += 1
        t = re.sub(r"\s+", " ", str(entrada.get("texto") or "")).strip()
        if t and not _texto_es_el_nombre(t, hallada.get("nombre") or nombre) and t not in hallada["textos"]:
            hallada["textos"].append(t)
        if reaccion:
            hallada.setdefault("reacciones", [])
            if isinstance(hallada.get("reacciones"), str):
                hallada["reacciones"] = _partir(hallada["reacciones"])
            polaridad, nombre_r = clasificar_reaccion(reaccion)
            if nombre_r not in hallada["reacciones"]:
                hallada["reacciones"].append(nombre_r)
                if polaridad == "negativa":
                    hallada["reacciones_neg"] = int(hallada.get("reacciones_neg") or 0) + 1
                else:
                    hallada["likes"] += 1
                    hallada["reacciones_pos"] = int(hallada.get("reacciones_pos") or 0) + 1
    pub = re.sub(r"\s+", " ", str(entrada.get("publicacion") or "")).strip()
    if pub and pub not in hallada["publicaciones"]:
        hallada["publicaciones"].append(pub[:300])
    return personas


def formatear_contacto(info, perfil=""):
    partes = []
    for item in info.get("contactos") or []:
        titulo = item.get("titulo") or "Contacto"
        contenido = item.get("contenido") or ""
        if contenido and "facebookmail" not in contenido.lower():
            partes.append(f"{titulo}: {contenido}")
    if info.get("ubicacion"):
        partes.append(info["ubicacion"])
    if perfil:
        partes.append(f"Perfil: {perfil}")
        partes.append("Escribir por Messenger desde el perfil.")
    return ". ".join(partes)


def acercamiento(persona, pagina_nombre=""):
    """Cómo hablarle según likes, comentarios, temas y ficha."""
    pagina = pagina_nombre or "la página"
    partes = []
    n_com = int(persona.get("comentarios") or 0)
    n_likes = int(persona.get("likes") or 0)
    n_pos = int(persona.get("reacciones_pos") or n_likes or 0)
    n_neg = int(persona.get("reacciones_neg") or 0)
    n_share = int(persona.get("compartidos") or 0)
    textos = persona.get("textos") if isinstance(persona.get("textos"), list) else _partir(persona.get("textos"))
    pubs = persona.get("publicaciones") if isinstance(persona.get("publicaciones"), list) else _partir(persona.get("publicaciones"))
    reacciones = persona.get("reacciones") if isinstance(persona.get("reacciones"), list) else _partir(persona.get("reacciones"))
    if textos:
        for t in textos:
            if not t:
                continue
            tono = tono_comentario(t)
            if tono == "desagrado":
                partes.append(f"Comentario en {pagina} (negativo): «{t}». Abordar con cuidado.")
            elif tono == "interés":
                partes.append(f"Comentario en {pagina} (positivo): «{t}». Responder a eso.")
            else:
                partes.append(f"Comentario en {pagina}: «{t}».")
    elif n_com:
        partes.append(f"Comentó {n_com} vez(ces) en {pagina}, pero Facebook no dejó leer el texto.")
    if n_share:
        partes.append(f"Compartió {n_share} publicación(es). El contenido le importó lo suficiente para reenviarlo.")
    if reacciones:
        partes.append("Reaccionó con: " + ", ".join(reacciones) + ".")
    elif n_neg or n_pos:
        detalle_neg = ", ".join(r for r in reacciones if r in {"Me enoja", "Me entristece"}) or "Me enoja o Me entristece"
        detalle_pos = ", ".join(r for r in reacciones if r not in {"Me enoja", "Me entristece"}) or "Me gusta"
        if n_neg:
            partes.append(f"{n_neg} reacción(es) negativa(s) ({detalle_neg}). Hay desagrado; no insistir con el mismo mensaje.")
        if n_pos:
            partes.append(f"{n_pos} reacción(es) positiva(s) ({detalle_pos}). Mostró interés en lo publicado.")
    mezcla = " ".join(list(textos or []) + list(pubs or []) + [persona.get("ficha") or ""])
    vistos = set()
    for cat in clasificar(mezcla)[:3]:
        if cat in vistos:
            continue
        vistos.add(cat)
        a = acercamiento_de_gusto(cat)
        if a:
            partes.append(a)
        prod = producto_de_gusto(cat)
        if prod:
            partes.append(f"Producto afín: {prod}.")
    contacto = (persona.get("contacto") or "").strip()
    if contacto:
        partes.append("Contacto: " + contacto)
    else:
        perfil = persona.get("perfil") or ""
        if perfil:
            partes.append(f"Contacto: mensaje directo en {perfil}.")
        else:
            partes.append("Contacto: mensaje directo desde su perfil de Facebook.")
    return " ".join(partes)


def hechos_de_interactuante(persona, pagina_nombre=""):
    """Hechos para la ficha: el comentario textual y el nombre de cada reacción."""
    pagina = pagina_nombre or "la página"
    hechos = []
    textos = persona.get("textos") if isinstance(persona.get("textos"), list) else _partir(persona.get("textos"))
    nombre = persona.get("nombre") or ""
    for i, t in enumerate(textos[:20], 1):
        t = str(t or "").strip()
        if not t or _texto_es_el_nombre(t, nombre):
            continue
        tono = tono_comentario(t)
        extra = ""
        if tono == "desagrado":
            extra = " Tono: negativo."
        elif tono == "interés":
            extra = " Tono: positivo."
        titulo = "Comentario" if i == 1 else f"Comentario ({i})"
        hechos.append({
            "categoria": "Comentario",
            "titulo": titulo,
            "contenido": f"Comentario en {pagina}: «{t}».{extra}",
        })
    n_pos = int(persona.get("reacciones_pos") or persona.get("likes") or 0)
    n_neg = int(persona.get("reacciones_neg") or 0)
    reacciones = persona.get("reacciones") if isinstance(persona.get("reacciones"), list) else _partir(persona.get("reacciones"))
    if not reacciones:
        if n_neg:
            reacciones = ["Me enoja"]
        elif n_pos:
            reacciones = ["Me gusta"]
    if reacciones:
        hechos.append({
            "categoria": "Reaccion",
            "titulo": "Reaccion",
            "contenido": f"En {pagina} reaccionó con: {', '.join(reacciones)}.",
        })
    elif n_pos or n_neg:
        partes = []
        if n_pos:
            partes.append(f"{n_pos} reacción(es) positiva(s)")
        if n_neg:
            partes.append(f"{n_neg} reacción(es) negativa(s)")
        hechos.append({
            "categoria": "Reaccion",
            "titulo": "Reaccion",
            "contenido": f"En {pagina}: " + ". ".join(partes) + ".",
        })
    return hechos


def persona_publica(p):
    nombre = p.get("nombre") or ""
    textos = p.get("textos") if isinstance(p.get("textos"), list) else _partir(p.get("textos"))
    textos = [t for t in textos if not _texto_es_el_nombre(t, nombre)]
    pubs = p.get("publicaciones") if isinstance(p.get("publicaciones"), list) else _partir(p.get("publicaciones"))
    reacciones = p.get("reacciones") if isinstance(p.get("reacciones"), list) else _partir(p.get("reacciones"))
    limpio = {
        **p,
        "nombre": nombre,
        "perfil": p.get("perfil") or "",
        "textos": textos,
        "reacciones": reacciones,
        "publicaciones": pubs,
    }
    return {
        "nombre": nombre,
        "perfil": p.get("perfil") or "",
        "likes": int(p.get("likes") or 0),
        "comentarios": int(p.get("comentarios") or 0),
        "compartidos": int(p.get("compartidos") or 0),
        "reacciones_pos": int(p.get("reacciones_pos") or p.get("likes") or 0),
        "reacciones_neg": int(p.get("reacciones_neg") or 0),
        "reacciones": reacciones,
        "textos": textos,
        "publicaciones": pubs,
        "ficha": p.get("ficha") or "",
        "contacto": p.get("contacto") or "",
        "acercamiento": acercamiento(limpio, p.get("pagina_nombre") or ""),
        "pagina_url": p.get("pagina_url") or p.get("pagina") or "",
        "pagina_nombre": p.get("pagina_nombre") or "",
        "fecha_actualizacion": str(p.get("fecha_actualizacion") or ""),
        "id": p.get("id"),
        "nueva": bool(p.get("nueva")),
        "ubicacion": (p.get("ubicacion") or "") or "",
        "de_colombia": es_de_colombia(limpio) is True,
    }


def asegurar_tabla():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for sentencia in DDL.split(";"):
                if sentencia.strip():
                    cur.execute(sentencia)
        conn.commit()
    finally:
        conn.close()


def _persistir_comentarios_contenido(personas, pagina_nombre=""):
    """Los comentarios y reacciones de interactuantes van a Revisión contenido."""
    from app.ingesta_linkedin import _guardar_publicacion, asegurar_tabla as asegurar_pubs

    pagina = pagina_nombre or "la página"
    asegurar_pubs()
    for p in personas or []:
        perfil = p.get("perfil") or ""
        if not perfil:
            continue
        nombre = (p.get("nombre") or perfil.rsplit("/", 1)[-1])[:180]
        textos = p.get("textos") if isinstance(p.get("textos"), list) else _partir(p.get("textos"))
        reacciones = p.get("reacciones") if isinstance(p.get("reacciones"), list) else _partir(p.get("reacciones"))
        quien = {"nombre": nombre, "clave_cliente": None}
        for t in textos:
            t = str(t or "").strip()
            if not t:
                continue
            _guardar_publicacion(quien, perfil, {
                "texto": t,
                "tipo": "comentario",
                "url_publicacion": perfil,
                "resumen": t,
            }, red="facebook")
        for r in reacciones:
            r = str(r or "").strip()
            if not r:
                continue
            _guardar_publicacion(quien, perfil, {
                "texto": f"Reaccionó con {r} en {pagina}.",
                "tipo": "reaccion",
                "url_publicacion": perfil,
                "resumen": r,
            }, red="facebook")


def persistir(pagina_url, pagina_nombre, personas):
    """Guarda o actualiza interactuantes. Devuelve cuántos se escribieron."""
    personas = [p for p in (personas or []) if es_relevante_colombia(p)]
    asegurar_tabla()
    conn = get_connection()
    n = 0
    try:
        with conn.cursor() as cur:
            for p in personas or []:
                perfil = p.get("perfil") or ""
                if not perfil:
                    continue
                nombre = (p.get("nombre") or perfil.rsplit("/", 1)[-1])[:180]
                textos = _unir(p.get("textos") if isinstance(p.get("textos"), list) else _partir(p.get("textos")))
                pubs = _unir(p.get("publicaciones") if isinstance(p.get("publicaciones"), list)
                             else _partir(p.get("publicaciones")))
                likes = int(p.get("likes") or 0)
                comentarios = int(p.get("comentarios") or 0)
                compartidos = int(p.get("compartidos") or 0)
                r_pos = int(p.get("reacciones_pos") or likes or 0)
                r_neg = int(p.get("reacciones_neg") or 0)
                reacs = _unir(p.get("reacciones") if isinstance(p.get("reacciones"), list)
                              else _partir(p.get("reacciones")))
                ficha = (p.get("ficha") or "")[:2000]
                contacto = (p.get("contacto") or "")[:800]
                acerc = (p.get("acercamiento") or acercamiento(p, pagina_nombre))[:1500]
                cur.execute("""SELECT likes, comentarios, textos, publicaciones, ficha, contacto, compartidos,
                                      reacciones_pos, reacciones_neg, reacciones
                               FROM public.interactuantes_pagina
                               WHERE pagina_url = %s AND persona_url = %s""",
                            (pagina_url, perfil))
                prev = cur.fetchone()
                if prev:
                    likes = max(likes, int(prev[0] or 0))
                    comentarios = max(comentarios, int(prev[1] or 0))
                    textos = _unir(_partir(prev[2]) + _partir(textos))
                    pubs = _unir(_partir(prev[3]) + _partir(pubs))
                    ficha = ficha or (prev[4] or "")
                    contacto = contacto or (prev[5] or "")
                    compartidos = max(compartidos, int(prev[6] or 0))
                    r_pos = max(r_pos, int(prev[7] or 0))
                    r_neg = max(r_neg, int(prev[8] or 0))
                    reacs = _unir(_partir(prev[9]) + _partir(reacs))
                cur.execute("""INSERT INTO public.interactuantes_pagina
                    (pagina_url, pagina_nombre, persona_url, nombre, likes, comentarios, compartidos,
                     reacciones_pos, reacciones_neg, reacciones,
                     textos, publicaciones, ficha, contacto, acercamiento, fecha_actualizacion)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
                    ON CONFLICT (pagina_url, persona_url) DO UPDATE SET
                      pagina_nombre = EXCLUDED.pagina_nombre,
                      nombre = EXCLUDED.nombre,
                      likes = EXCLUDED.likes,
                      comentarios = EXCLUDED.comentarios,
                      compartidos = EXCLUDED.compartidos,
                      reacciones_pos = EXCLUDED.reacciones_pos,
                      reacciones_neg = EXCLUDED.reacciones_neg,
                      reacciones = EXCLUDED.reacciones,
                      textos = EXCLUDED.textos,
                      publicaciones = EXCLUDED.publicaciones,
                      ficha = EXCLUDED.ficha,
                      contacto = EXCLUDED.contacto,
                      acercamiento = EXCLUDED.acercamiento,
                      fecha_actualizacion = now()""",
                            (pagina_url, pagina_nombre or "", perfil, nombre, likes, comentarios, compartidos,
                             r_pos, r_neg, reacs, textos, pubs, ficha, contacto, acerc))
                n += 1
        conn.commit()
    finally:
        conn.close()
    _persistir_hechos(personas, pagina_nombre)
    _persistir_comentarios_contenido(personas, pagina_nombre)
    return n


def _persistir_hechos(personas, pagina_nombre):
    """Deja el comentario acotado y las reacciones en la ficha de cada persona."""
    from app.ingesta_perfiles import _guardar, asegurar_tabla, registrar_perfil_leido

    asegurar_tabla()
    from app.ingesta_actividad import hechos_desde_info
    for p in personas or []:
        perfil = p.get("perfil") or ""
        if not perfil:
            continue
        hechos = hechos_de_interactuante(p, pagina_nombre)
        extra = p.get("info") if isinstance(p.get("info"), dict) else {}
        if not extra and p.get("ficha"):
            from facebook_activity_scraper import parsear_ficha_facebook
            extra = parsear_ficha_facebook(p.get("ficha")) or {}
        textos = p.get("textos") if isinstance(p.get("textos"), list) else _partir(p.get("textos"))
        posts = [{"tipo": "publicacion", "texto": t} for t in textos if t]
        if extra or posts:
            hechos.extend(hechos_desde_info(extra, posts, incluir_red=False))
        if not hechos:
            continue
        nombre = (p.get("nombre") or perfil.rsplit("/", 1)[-1])[:180]
        _guardar({"nombre": nombre, "clave_cliente": None}, "facebook", perfil, hechos)
        try:
            registrar_perfil_leido(nombre, "facebook", perfil)
        except Exception:
            pass


def listar(pagina_url=None, limite=5000):
    asegurar_tabla()
    limite = min(max(int(limite or 5000), 1), 5000)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if pagina_url:
                cur.execute("""SELECT id, pagina_url, pagina_nombre, persona_url AS perfil, nombre,
                                      likes, comentarios, compartidos, reacciones_pos, reacciones_neg, reacciones,
                                      textos, publicaciones, ficha, contacto,
                                      acercamiento, fecha_actualizacion
                               FROM public.interactuantes_pagina
                               WHERE pagina_url = %s
                               ORDER BY comentarios DESC, compartidos DESC, reacciones_neg DESC, likes DESC, fecha_actualizacion DESC
                               LIMIT %s""", (pagina_url, limite))
            else:
                cur.execute("""SELECT id, pagina_url, pagina_nombre, persona_url AS perfil, nombre,
                                      likes, comentarios, compartidos, reacciones_pos, reacciones_neg, reacciones,
                                      textos, publicaciones, ficha, contacto,
                                      acercamiento, fecha_actualizacion
                               FROM public.interactuantes_pagina
                               ORDER BY fecha_actualizacion DESC, comentarios DESC, compartidos DESC, likes DESC
                               LIMIT %s""", (limite,))
            cols = [d[0] for d in cur.description]
            return [persona_publica(dict(zip(cols, r))) for r in cur.fetchall()
                    if es_relevante_colombia(dict(zip(cols, r)))]
    finally:
        conn.close()


def _sembrar_mapfre():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO public.paginas_seguros (url, nombre)
                           VALUES (%s, 'MAPFRE Colombia')
                           ON CONFLICT (url) DO NOTHING""", (PAGINA_DEFECTO,))
        conn.commit()
    finally:
        conn.close()


def listar_paginas():
    asegurar_tabla()
    _sembrar_mapfre()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT url, nombre, fecha_alta FROM public.paginas_seguros
                           ORDER BY (url = %s) DESC, nombre, url""", (PAGINA_DEFECTO,))
            return [{"url": r[0], "nombre": r[1] or r[0].rsplit("/", 1)[-1],
                     "fija": r[0] == PAGINA_DEFECTO} for r in cur.fetchall()]
    finally:
        conn.close()


def agregar_pagina(url, nombre=""):
    url = clasificar_url_pagina(url)
    if not url:
        return None
    asegurar_tabla()
    _sembrar_mapfre()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO public.paginas_seguros (url, nombre)
                           VALUES (%s, %s)
                           ON CONFLICT (url) DO UPDATE SET nombre = COALESCE(NULLIF(EXCLUDED.nombre, ''), paginas_seguros.nombre)
                           RETURNING url, nombre""",
                        (url, (nombre or url.rsplit("/", 1)[-1])[:180]))
            fila = cur.fetchone()
        conn.commit()
        return {"url": fila[0], "nombre": fila[1], "fija": fila[0] == PAGINA_DEFECTO}
    finally:
        conn.close()


def quitar_pagina(url):
    url = clasificar_url_pagina(url) or (url or "").strip()
    if not url or url == PAGINA_DEFECTO:
        return False
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.paginas_seguros WHERE url = %s AND url <> %s",
                        (url, PAGINA_DEFECTO))
            n = cur.rowcount
        conn.commit()
        return n > 0
    finally:
        conn.close()


def listar_recopilar():
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT url, red, nombre, origen, fecha_alta
                           FROM public.perfiles_recopilar ORDER BY fecha_alta DESC""")
            return [{"url": r[0], "red": r[1], "nombre": r[2], "origen": r[3]} for r in cur.fetchall()]
    finally:
        conn.close()


def pasar_otras_redes_hechos_a_urls():
    """Saca de Revisión de hechos los 'Otra red' y los deja en URLs perfiles."""
    from app.perfil_redes import _URL_EN_TEXTO
    asegurar_tabla()
    conn = get_connection()
    n = 0
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT nombre, contenido FROM public.hechos_perfil
                           WHERE categoria = 'Otra red'""")
            filas = list(cur.fetchall() or [])
        for nombre, contenido in filas:
            origen = f"encontrado en {nombre}"[:80] if nombre else "otra red"
            for m in _URL_EN_TEXTO.finditer(contenido or ""):
                if agregar_recopilar(m.group(0).rstrip(".,);'\""), origen=origen):
                    n += 1
        if filas:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM public.hechos_perfil WHERE categoria = 'Otra red'")
            conn.commit()
        return n
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return n
    finally:
        conn.close()


def agregar_recopilar(url, nombre="", origen=""):
    from app.perfil_redes import clasificar_url
    hallado = clasificar_url(url)
    if not hallado:
        return None
    red, limpia = hallado
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO public.perfiles_recopilar (url, red, nombre, origen)
                           VALUES (%s, %s, %s, %s)
                           ON CONFLICT (url) DO UPDATE SET
                             nombre = COALESCE(NULLIF(EXCLUDED.nombre, ''), perfiles_recopilar.nombre),
                             origen = COALESCE(NULLIF(EXCLUDED.origen, ''), perfiles_recopilar.origen)
                           RETURNING url, red, nombre, origen""",
                        (limpia, red, (nombre or "")[:180], (origen or "")[:80]))
            fila = cur.fetchone()
        conn.commit()
        return {"url": fila[0], "red": fila[1], "nombre": fila[2], "origen": fila[3]}
    finally:
        conn.close()


def quitar_recopilar(url):
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.perfiles_recopilar WHERE url = %s", ((url or "").strip(),))
            n = cur.rowcount
        conn.commit()
        return n > 0
    finally:
        conn.close()


def quitar_interactuante(persona_url, pagina_url=None):
    """Quita a una persona de la lista de URLs. No borra hechos ya leídos."""
    url = (persona_url or "").strip()
    if not url:
        return False
    asegurar_tabla()
    n = 0
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if pagina_url:
                cur.execute(
                    "DELETE FROM public.interactuantes_pagina WHERE persona_url = %s AND pagina_url = %s",
                    (url, pagina_url))
            else:
                cur.execute(
                    "DELETE FROM public.interactuantes_pagina WHERE persona_url = %s", (url,))
            n += cur.rowcount
        conn.commit()
    finally:
        conn.close()
    if quitar_recopilar(url):
        n += 1
    return n > 0


def listar_posibles():
    """Personas leídas en páginas de seguros (MAPFRE y las demás). Solo Colombia."""
    personas = listar(None, limite=5000)
    for p in personas:
        p["origen"] = p.get("pagina_nombre") or "página de seguros"
    return personas


def pasar_interactuantes_a_recopilar(pagina_url=None):
    """Copia a la lista general las URLs de quien ya interactuó (MAPFRE u otra página)."""
    n = 0
    for p in listar(pagina_url, limite=5000):
        if agregar_recopilar(p.get("perfil") or "", p.get("nombre") or "",
                             origen=p.get("pagina_nombre") or "pagina"):
            n += 1
    return n
