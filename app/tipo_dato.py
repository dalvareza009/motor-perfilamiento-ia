"""Una etiqueta principal por texto: no se mezcla ficha con contenido.

Trabajo = cargo actual. Experiencia = empleos que ya terminaron.
Estudios = formación formal (universidad, colegio, título).
Cursos = diplomados, certificaciones, talleres, Platzi, Coursera.
Descripcion = bio / acerca de (quién dice ser).
Informacion = dato de perfil que no es cargo, estudio ni bio.
Publicacion = post o restack. Mensaje = comentario, respuesta o DM.
"""
import re
import unicodedata

TIPOS_FICHA = (
    "Trabajo", "Experiencia", "Estudios", "Cursos",
    "Descripcion", "Informacion",
)
TIPOS_CONTENIDO = ("Publicacion", "Mensaje", "Comentario", "Reaccion")

_MENSAJE = {
    "comentario", "comment", "reply", "respuesta", "mensaje", "message", "dm",
}
_REACCION = {"reaccion", "like", "reaction"}
_PUBLICACION = {
    "publicacion", "post", "compartida", "repost", "restack", "share", "nota",
}


def _n(texto):
    t = unicodedata.normalize("NFD", str(texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


_CURSO = re.compile(
    r"\b(cursos?|diplomados?|certificacion(?:es)?|certificados?|"
    r"talleres?|workshops?|bootcamps?|seminarios?|capacitaciones?|"
    r"platzi|coursera|udemy|\bedx\b|linkedin learning|sena virtual|"
    r"moocs?|credencial|badge de)\b"
)
_GRADO = re.compile(
    r"\b(pregrado|posgrado|maestr\w*|doctorad\w*|\bmba\b|bachiller\w*|"
    r"licenciatura|ingenier[ií]a|especializacion universitaria|"
    r"titulo profesional)\b"
)
_ESTUDIO = re.compile(
    r"\b(universidad|universitario|colegio|estudiante|egresad\w*|"
    r"me gradue|soy graduad|estudie|estoy estudiando|soy estudiante|"
    r"student|university|college|semestre de)\b"
)
_CARGO = re.compile(
    r"\b(analista|gerente|coordinador[ae]?|asesor[ae]?|docente|profesor[ae]?|"
    r"abogad[oa]|desarrollador[ae]?|contador[ae]?|medic[oa]|enfermer[oa]|"
    r"ingenier[oa]|emprendedor[ae]?|empresari[oa]|profesional|coach|chef|"
    r"comerciante|practicante|pasante|periodista|investigador[ae]?)\b"
)
_VERBO_TRABAJO = re.compile(
    r"\b(trabajo|trabaja|trabaje|empleo|experiencia laboral|"
    r"me dedico|emprendo|trabajo (?:en|como|de))\b"
)
_PASADO = re.compile(
    r"\b(trabaje|trabajaba|fui\b|era\b|estuve|ex[- ]|anteriormente|"
    r"antes (?:era|fui|trabaj)|hasta (?:el )?\d{4}|de \d{4} a \d{4})\b"
)
_RANGO_PASADO = re.compile(
    r"\(\s*(?:\d{4}|\?)\s*[-–]\s*(?!actualidad|presente|present|hoy)(\d{4})\s*\)",
    re.I,
)
_ACTUAL = re.compile(
    r"\b(actualmente|hoy trabajo|trabajo (?:en|como|de)|me dedico|"
    r"actualidad|presente)\b"
)
_YO_ESTUDIO = re.compile(
    r"\b(me gradue|soy graduad|egres[ée]|estudie|soy estudiante|"
    r"recien graduad|recien egresad|"
    r"termine (?:la |el )?(?:carrera|maestr\w*|pregrado|universidad|colegio))\b"
)
_BIO = re.compile(
    r"\b(me apasiona|soy de las que|escribo sobre|amante de|"
    r"acerca de mi|sobre mi)\b"
)


def tipo_contenido(tipo_post, origen=""):
    """Publicacion, Mensaje o Reaccion según el tipo de pieza extraída."""
    t = _n(tipo_post or "")
    o = _n(origen or "")
    if t in _MENSAJE or o in ("comentario", "mensaje"):
        return "Mensaje"
    if t in _REACCION or o == "reaccion":
        return "Reaccion"
    if t in _PUBLICACION or o == "publicacion":
        return "Publicacion"
    if t:
        return "Publicacion"
    return ""


def es_contenido(tipo_post, origen=""):
    return tipo_contenido(tipo_post, origen) in TIPOS_CONTENIDO and origen != "ficha"


def eje_ficha(texto, seccion=None, default=None):
    """Etiqueta de ficha. Trabajo, Experiencia, Estudios y Cursos no se pisan."""
    n = _n(texto)
    if len(n) < 3:
        return default
    seccion = seccion or ""
    curso = bool(_CURSO.search(n))
    grado = bool(_GRADO.search(n))
    estudio = bool(_ESTUDIO.search(n)) or seccion == "Estudios"
    cargo = bool(_CARGO.search(n))
    verbo = bool(_VERBO_TRABAJO.search(n))
    pasado = bool(_PASADO.search(n) or _RANGO_PASADO.search(n))
    yo_estudio = bool(_YO_ESTUDIO.search(n))
    actual = bool(_ACTUAL.search(n))

    if seccion == "Cursos" or (curso and not grado):
        return "Cursos"
    if estudio and not (cargo and not yo_estudio and seccion != "Estudios"):
        return "Estudios"
    if (pasado and not actual) and (cargo or verbo or seccion == "Trabajo"):
        return "Experiencia"
    if cargo or verbo or seccion == "Trabajo":
        return "Trabajo"
    if seccion == "Descripcion" or (_BIO.search(n) and not cargo and not estudio):
        return "Descripcion"
    if seccion == "Informacion":
        return "Informacion"
    return default


def clasificar(texto, seccion=None, origen="ficha", tipo_post=""):
    """Una sola etiqueta para el revisor y para la ficha."""
    contenido = tipo_contenido(tipo_post, origen)
    if origen in ("comentario", "mensaje") or contenido == "Mensaje":
        return "Mensaje"
    if contenido == "Reaccion":
        return "Reaccion"
    if origen in ("publicacion", "restack") or (
            contenido == "Publicacion" and origen != "ficha"):
        eje = eje_ficha(texto, seccion)
        return eje or "Publicacion"
    eje = eje_ficha(texto, seccion)
    if eje:
        return eje
    if origen == "ficha" and len(_n(texto)) >= 40:
        return "Descripcion"
    return "Informacion" if origen == "ficha" else (contenido or "Informacion")
