"""Publicaciones de todas las redes, separadas de la ficha (estudios, cargos, logros).

Un scraping de perfil alimenta las dos ventanas: hechos (información declarada)
y contenido (lo que la persona publica o comenta).
"""
import re
import unicodedata

from app.database import get_connection
from app.redes_seguidas import CATEGORIAS_RED

CATEGORIAS_CONTENIDO = ("Publicacion", "Comentario", "Reaccion", "Resumen de contenido")
CATEGORIAS_NO_FICHA = tuple(CATEGORIAS_RED) + CATEGORIAS_CONTENIDO
CAMPOS_NO_DESDE_PUBLICACION = ("experiencia", "educacion", "estado_laboral", "estado_academico")


def excluidas_de_ficha():
    return list(CATEGORIAS_NO_FICHA)


NOTA_NO_DISPONIBLE = "Contenido no disponible."
NOTA_NO_ELEGIBLE = "Contenido no elegible."

_MARCAS_TECNICAS = (
    '"require":', "qpltimings", "hastesupportdata", "splash_screen",
    "clpdata", "polaris", '"r":1', '"s":1', "timingserverjs",
    "serverjs", "scheduledserverjs",
)
_NO_DISPONIBLE = (
    "este contenido no esta disponible",
    "this content isn't available",
    "this content isnt available",
    "contenido no esta disponible",
    "esta pagina no esta disponible",
    "sorry, this page isn't available",
    "this page isn't available",
    "no esta disponible en este momento",
)
_LINEAS_CROMATICAS = {
    "escribe algo", "escribe algo...", "perfil", "me gusta", "comentar",
    "compartir", "seguir", "ver traduccion", "see translation", "responder",
    "ver mas", "see more", "mostrar mas", "show more", "leer mas", "read more",
    "like", "comment", "share", "guardar", "a",
}
_VER_MAS_FIN = re.compile(
    r"[\s.]*\b(ver m[aá]s|see more|mostrar m[aá]s|show more|leer m[aá]s|read more|"
    r"… m[aá]s|\.{2,3}\s*m[aá]s)\s*$",
    re.I,
)
_PIE_RED = {
    "empleo", "jobs", "ayuda", "help", "api", "privacidad", "privacy",
    "condiciones", "terms", "terminos", "ubicaciones", "locations", "popular",
    "instagram lite", "meta ai", "muse", "meta", "blog", "cookies",
    "informacion", "acerca de", "about", "from meta", "de meta",
    "subir contactos y personas no usuarias", "subir contactos",
    "personas no usuarias", "instagram", "threads", "imprint", "impresum",
    "centro de ayuda", "developers", "prensa", "press",
}
_IDIOMAS = {
    "afrikaans", "arabic", "bahasa indonesia", "bahasa malaysia", "cestina",
    "cesky", "dansk", "deutsch", "ellhnika", "english", "english (uk)",
    "english (us)", "espanol", "espanol (espana)", "espanol (mexico)",
    "filipino", "finnish", "francais", "francais (france)", "hindi", "italiano",
    "magyar", "nederlands", "norsk", "polski", "portugues",
    "portugues (brasil)", "portugues (portugal)", "romana", "suomi", "svenska",
    "turkce", "tieng viet", "chinese", "japanese", "korean",
}


def _sin_tilde(texto):
    t = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def es_volcado_tecnico(texto):
    """JSON interno de Instagram/Facebook, no un caption."""
    t = str(texto or "")
    bajo = _sin_tilde(t)
    if any(_sin_tilde(m) in bajo for m in _MARCAS_TECNICAS):
        return True
    if t.lstrip().startswith(("{", "[")) and (t.count('":') >= 6 or t.count("':") >= 6):
        return True
    if t.count("{") >= 4 and ('"r"' in t or "'r'" in t):
        return True
    if len(t) >= 80:
        letras = sum(c.isalpha() for c in t)
        if letras / len(t) < 0.28:
            return True
    return False


def es_aviso_no_disponible(texto):
    bajo = _sin_tilde(texto)
    return any(m in bajo for m in _NO_DISPONIBLE)


def quitar_ver_mas(texto):
    """Quita el botón 'ver más' que quedó pegado al caption ya expandido."""
    lineas = []
    for ln in str(texto or "").splitlines():
        t = _VER_MAS_FIN.sub("", ln).strip(" .")
        if t and _sin_tilde(t) not in _LINEAS_CROMATICAS:
            lineas.append(t)
    return "\n".join(lineas)


def _es_cromo(linea):
    t = re.sub(r"\s+", " ", linea or "").strip(" .")
    bajo = _sin_tilde(t)
    if not bajo or bajo in _LINEAS_CROMATICAS:
        return True
    if re.fullmatch(r"a?\s*\d{1,3}", bajo):
        return True
    if bajo.startswith("por lo general, esto sucede"):
        return True
    if re.match(r"^(perfil\s+)?\d{1,2}/\d{1,2}/\d{2,4}", bajo):
        return True
    return False


def _es_linea_pie(linea):
    """Enlace legal, idioma o pie de Instagram/Facebook/Meta. No es un caption."""
    t = re.sub(r"\s+", " ", linea or "").strip(" .")
    bajo = _sin_tilde(t)
    if not bajo:
        return True
    if bajo in _PIE_RED or bajo in _IDIOMAS:
        return True
    if bajo.startswith("subir contactos") or "instagram lite" in bajo or "meta ai" in bajo:
        return True
    if re.fullmatch(r"[a-z]{2,24}(\s*\([a-z ]{2,24}\))?", bajo) and bajo.split("(")[0].strip() in _IDIOMAS:
        return True
    return False


def es_pie_de_interfaz(texto):
    """True si el bloque es el pie de la red (idiomas, privacidad, Meta AI…)."""
    crudo = str(texto or "").strip()
    if not crudo:
        return False
    lineas = [ln.strip() for ln in crudo.splitlines() if ln.strip()]
    if len(lineas) <= 1:
        lineas = [p.strip() for p in re.split(r"\s{2,}|\s*\|\s*", crudo) if p.strip()] or lineas
    pie = sum(1 for ln in lineas if _es_linea_pie(ln) or _es_cromo(ln))
    if pie >= 4 and pie >= max(1, len(lineas) * 0.5):
        return True
    bajo = _sin_tilde(crudo)
    marcas = ("privacidad", "condiciones", "instagram lite", "meta ai", "ubicaciones", "empleo")
    return sum(1 for m in marcas if m in bajo) >= 3


def acotar(texto, n=220):
    """Deja el caption corto, sin cortar a mitad de palabra."""
    t = re.sub(r"\s+", " ", str(texto or "")).strip()
    if len(t) <= n:
        return t
    corte = t[:n].rsplit(" ", 1)[0].strip()
    return (corte or t[:n]).rstrip(".,;:") + "…"


def describir_publicacion(post):
    """Caption acotado, si hay imagen y de qué trata. None si es ruido de interfaz."""
    from app.gustos import clasificar

    post = post or {}
    limpio, estado = texto_mostrable(post.get("texto") or "")
    if estado == "omitir":
        return None
    acotado = acotar(limpio, 220) if estado == "ok" else limpio
    alts = [re.sub(r"\s+", " ", a).strip()
            for a in (post.get("alts") or []) if isinstance(a, str) and len(a.strip()) > 8]
    n_img = int(post.get("n_imagenes") or post.get("imagenes") or 0)
    if not n_img:
        n_img = len(alts) or (1 if post.get("tiene_imagenes") else 0)
    tiene = bool(n_img or post.get("tiene_imagenes") or alts)
    mezcla = " ".join(p for p in (acotado if estado == "ok" else "", *alts[:3]) if p)
    temas = clasificar(mezcla)[:3] if mezcla else []
    partes = []
    if tiene:
        partes.append("Incluye imagen." if n_img <= 1 else f"Incluye {n_img} imágenes.")
    if temas:
        partes.append("Trata de " + ", ".join(t.lower() for t in temas) + ".")
    elif estado == "ok" and acotado:
        partes.append("Publicó: " + acotar(acotado, 140))
    elif tiene:
        partes.append("Publicó una imagen sin descripción.")
    else:
        partes.append("Publicó contenido sin un tema claro.")
    return {
        "texto": acotado,
        "resumen": " ".join(partes),
        "tiene_imagenes": tiene,
        "n_imagenes": n_img,
        "estado": estado,
        "temas": temas,
    }


def resumir_actividad(posts):
    """Una frase de lo que publica la persona en el conjunto de piezas."""
    piezas = [describir_publicacion(p) for p in posts or []]
    piezas = [p for p in piezas if p]
    if not piezas:
        return ""
    n_img = sum(1 for p in piezas if p["tiene_imagenes"])
    temas, vistos = [], set()
    for p in piezas:
        for t in p.get("temas") or []:
            if t not in vistos:
                vistos.add(t)
                temas.append(t)
    partes = [f"Publicó {len(piezas)} pieza(s)."]
    if n_img:
        partes.append(f"{n_img} con imagen.")
    if temas:
        partes.append("Temas: " + ", ".join(temas[:5]) + ".")
    return " ".join(partes)


def texto_mostrable(texto):
    """Quita volcados técnicos y avisos de la red. -> (texto, estado).

    estado: ok | no_disponible | no_elegible
    """
    crudo = quitar_ver_mas(str(texto or "").strip())
    if not crudo:
        return "", "omitir"
    if es_volcado_tecnico(crudo):
        return NOTA_NO_ELEGIBLE, "no_elegible"
    if es_aviso_no_disponible(crudo):
        return NOTA_NO_DISPONIBLE, "no_disponible"
    lineas = [ln.strip() for ln in crudo.splitlines()
              if ln.strip() and not _es_cromo(ln) and not _es_linea_pie(ln)]
    limpio = "\n".join(lineas).strip()
    if not limpio or es_pie_de_interfaz(limpio):
        return "", "omitir"
    if es_volcado_tecnico(limpio):
        return NOTA_NO_ELEGIBLE, "no_elegible"
    if es_aviso_no_disponible(limpio):
        return NOTA_NO_DISPONIBLE, "no_disponible"
    return limpio, "ok"


def listar(nombre="", red="", limite=500):
    """Publicaciones guardadas + comentarios/reacciones de la misma persona."""
    from app.ingesta_linkedin import asegurar_tabla
    from app.ingesta_perfiles import asegurar_tabla as asegurar_hechos

    asegurar_tabla()
    asegurar_hechos()
    nombre = (nombre or "").strip()
    red = (red or "").strip().lower()
    limite = max(1, min(int(limite or 500), 2000))
    items = []
    total = 0
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT COUNT(*) FROM public.publicaciones_linkedin
                           WHERE (%s = '' OR LOWER(nombre) = LOWER(%s))
                             AND (%s = '' OR LOWER(COALESCE(red, 'linkedin')) = %s)""",
                        (nombre, nombre, red, red))
            total += int(cur.fetchone()[0] or 0)
            cur.execute("""SELECT COUNT(*) FROM public.hechos_perfil
                           WHERE categoria = ANY(%s)
                             AND (%s = '' OR LOWER(nombre) = LOWER(%s))
                             AND (%s = '' OR LOWER(red) = %s)""",
                        (list(CATEGORIAS_CONTENIDO), nombre, nombre, red, red))
            total += int(cur.fetchone()[0] or 0)
            cur.execute("""SELECT id_publicacion, nombre, clave_cliente,
                                  COALESCE(red, 'linkedin') AS red, fuente_url, texto, tiempo,
                                  COALESCE(url_publicacion, '') AS url_publicacion,
                                  COALESCE(tipo, 'publicacion') AS tipo, fecha_extraccion,
                                  COALESCE(resumen, '') AS resumen,
                                  COALESCE(tiene_imagenes, FALSE) AS tiene_imagenes,
                                  COALESCE(n_imagenes, 0) AS n_imagenes
                           FROM public.publicaciones_linkedin
                           WHERE (%s = '' OR LOWER(nombre) = LOWER(%s))
                             AND (%s = '' OR LOWER(COALESCE(red, 'linkedin')) = %s)
                           ORDER BY fecha_extraccion DESC, id_publicacion DESC
                           LIMIT %s""",
                        (nombre, nombre, red, red, limite))
            cols = [d[0] for d in cur.description]
            for fila in cur.fetchall():
                p = dict(zip(cols, fila))
                tipo = p.get("tipo") or "publicacion"
                texto, estado = texto_mostrable(p.get("texto") or "")
                if estado == "omitir":
                    total = max(0, total - 1)
                    continue
                items.append({
                    "origen": "publicacion",
                    "id": p["id_publicacion"],
                    "nombre": p.get("nombre") or "",
                    "clave_cliente": p.get("clave_cliente") or "",
                    "red": p.get("red") or "linkedin",
                    "tipo": tipo,
                    "texto": texto,
                    "resumen": p.get("resumen") or "",
                    "tiene_imagenes": bool(p.get("tiene_imagenes")),
                    "n_imagenes": int(p.get("n_imagenes") or 0),
                    "estado": estado,
                    "tiempo": p.get("tiempo") or "",
                    "url": (p.get("url_publicacion") or "").strip() or (p.get("fuente_url") or ""),
                    "fuente_url": p.get("fuente_url") or "",
                    "fecha": str(p.get("fecha_extraccion") or ""),
                })
            cur.execute("""SELECT id_hecho, nombre, clave_cliente, red, fuente_url,
                                  categoria, titulo, contenido, fecha_actualizacion
                           FROM public.hechos_perfil
                           WHERE categoria = ANY(%s)
                             AND (%s = '' OR LOWER(nombre) = LOWER(%s))
                             AND (%s = '' OR LOWER(red) = %s)
                           ORDER BY fecha_actualizacion DESC, id_hecho DESC
                           LIMIT %s""",
                        (list(CATEGORIAS_CONTENIDO), nombre, nombre, red, red, limite))
            cols = [d[0] for d in cur.description]
            for fila in cur.fetchall():
                h = dict(zip(cols, fila))
                texto, estado = texto_mostrable(h.get("contenido") or h.get("titulo") or "")
                if estado == "omitir":
                    total = max(0, total - 1)
                    continue
                items.append({
                    "origen": "hecho",
                    "id": h["id_hecho"],
                    "nombre": h.get("nombre") or "",
                    "clave_cliente": h.get("clave_cliente") or "",
                    "red": h.get("red") or "",
                    "tipo": (h.get("categoria") or "Publicacion").lower(),
                    "texto": texto,
                    "estado": estado,
                    "tiempo": "",
                    "url": h.get("fuente_url") or "",
                    "fuente_url": h.get("fuente_url") or "",
                    "fecha": str(h.get("fecha_actualizacion") or ""),
                    "titulo": h.get("titulo") or "",
                    "categoria": h.get("categoria") or "",
                })
    finally:
        conn.close()
    items.sort(key=lambda x: x.get("fecha") or "", reverse=True)
    return {"total": total, "items": items[:limite]}
