"""Personas que interactúan con una página de Facebook (likes, comentarios y shares).

La página (por ejemplo MAPFRE) se lee con la sesión de Chrome. De cada
publicación se sacan quienes reaccionaron, comentaron o compartieron, el enlace
a su perfil y, si Facebook lo muestra, ficha y contacto para acercarse.
"""
import re
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
"""


def _host(url):
    return (urlparse(url or "").hostname or "").lower().removeprefix("www.").removeprefix("m.")


def _partes(url):
    return [unquote(s) for s in urlparse(url or "").path.split("/") if s]


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


def _unir(valores, sep=" | "):
    vistos, partes = set(), []
    for v in valores or []:
        t = re.sub(r"\s+", " ", str(v or "")).strip()
        if t and t.lower() not in vistos:
            vistos.add(t.lower())
            partes.append(t[:400])
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
    if hallada is None:
        hallada = {
            "nombre": nombre or perfil.rsplit("/", 1)[-1].replace(".", " "),
            "perfil": perfil,
            "likes": 0,
            "comentarios": 0,
            "compartidos": 0,
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
    if tipo in {"like", "reaccion", "reacción", "me gusta"}:
        hallada["likes"] += 1
    elif tipo in {"compartido", "compartida", "share", "shares"}:
        hallada["compartidos"] = int(hallada.get("compartidos") or 0) + 1
    elif tipo in {"comentario", "comment"}:
        hallada["comentarios"] += 1
        t = re.sub(r"\s+", " ", str(entrada.get("texto") or "")).strip()
        if t and t not in hallada["textos"]:
            hallada["textos"].append(t[:400])
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
    n_share = int(persona.get("compartidos") or 0)
    textos = persona.get("textos") if isinstance(persona.get("textos"), list) else _partir(persona.get("textos"))
    pubs = persona.get("publicaciones") if isinstance(persona.get("publicaciones"), list) else _partir(persona.get("publicaciones"))
    if n_com:
        if textos:
            partes.append(f"Comentó en {pagina}: «{textos[0][:180]}». Responder a eso.")
        else:
            partes.append(f"Comentó {n_com} vez(ces) en {pagina}. Ya abrió conversación.")
    if n_share:
        partes.append(f"Compartió {n_share} publicación(es). El contenido le importó lo suficiente para reenviarlo.")
    if n_likes:
        partes.append(f"Le dio me gusta a {n_likes} publicación(es). Mostró interés en lo publicado.")
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


def persona_publica(p):
    textos = p.get("textos") if isinstance(p.get("textos"), list) else _partir(p.get("textos"))
    pubs = p.get("publicaciones") if isinstance(p.get("publicaciones"), list) else _partir(p.get("publicaciones"))
    return {
        "nombre": p.get("nombre") or "",
        "perfil": p.get("perfil") or "",
        "likes": int(p.get("likes") or 0),
        "comentarios": int(p.get("comentarios") or 0),
        "compartidos": int(p.get("compartidos") or 0),
        "textos": textos,
        "publicaciones": pubs,
        "ficha": p.get("ficha") or "",
        "contacto": p.get("contacto") or "",
        "acercamiento": p.get("acercamiento") or "",
        "pagina_url": p.get("pagina_url") or p.get("pagina") or "",
        "pagina_nombre": p.get("pagina_nombre") or "",
        "fecha_actualizacion": str(p.get("fecha_actualizacion") or ""),
        "id": p.get("id"),
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


def persistir(pagina_url, pagina_nombre, personas):
    """Guarda o actualiza interactuantes. Devuelve cuántos se escribieron."""
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
                ficha = (p.get("ficha") or "")[:2000]
                contacto = (p.get("contacto") or "")[:800]
                acerc = (p.get("acercamiento") or acercamiento(p, pagina_nombre))[:1500]
                cur.execute("""SELECT likes, comentarios, textos, publicaciones, ficha, contacto, compartidos
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
                cur.execute("""INSERT INTO public.interactuantes_pagina
                    (pagina_url, pagina_nombre, persona_url, nombre, likes, comentarios, compartidos,
                     textos, publicaciones, ficha, contacto, acercamiento, fecha_actualizacion)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
                    ON CONFLICT (pagina_url, persona_url) DO UPDATE SET
                      pagina_nombre = EXCLUDED.pagina_nombre,
                      nombre = EXCLUDED.nombre,
                      likes = EXCLUDED.likes,
                      comentarios = EXCLUDED.comentarios,
                      compartidos = EXCLUDED.compartidos,
                      textos = EXCLUDED.textos,
                      publicaciones = EXCLUDED.publicaciones,
                      ficha = EXCLUDED.ficha,
                      contacto = EXCLUDED.contacto,
                      acercamiento = EXCLUDED.acercamiento,
                      fecha_actualizacion = now()""",
                            (pagina_url, pagina_nombre or "", perfil, nombre, likes, comentarios, compartidos,
                             textos, pubs, ficha, contacto, acerc))
                n += 1
        conn.commit()
    finally:
        conn.close()
    return n


def listar(pagina_url=None, limite=200):
    asegurar_tabla()
    limite = min(max(int(limite or 200), 1), 500)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if pagina_url:
                cur.execute("""SELECT id, pagina_url, pagina_nombre, persona_url AS perfil, nombre,
                                      likes, comentarios, compartidos, textos, publicaciones, ficha, contacto,
                                      acercamiento, fecha_actualizacion
                               FROM public.interactuantes_pagina
                               WHERE pagina_url = %s
                               ORDER BY comentarios DESC, compartidos DESC, likes DESC, fecha_actualizacion DESC
                               LIMIT %s""", (pagina_url, limite))
            else:
                cur.execute("""SELECT id, pagina_url, pagina_nombre, persona_url AS perfil, nombre,
                                      likes, comentarios, compartidos, textos, publicaciones, ficha, contacto,
                                      acercamiento, fecha_actualizacion
                               FROM public.interactuantes_pagina
                               ORDER BY fecha_actualizacion DESC, comentarios DESC, compartidos DESC, likes DESC
                               LIMIT %s""", (limite,))
            cols = [d[0] for d in cur.description]
            return [persona_publica(dict(zip(cols, r))) for r in cur.fetchall()]
    finally:
        conn.close()
