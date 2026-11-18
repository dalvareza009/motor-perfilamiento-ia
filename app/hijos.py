"""Señales de hijos en un perfil: bio, ficha, captions, alts y contenidos compartidos.

Cada perfil se revisa entero. Solo se afirma que tiene hijos con declaración
propia (mamá de, mi hijo, hijo etiquetado, caption de foto). Compartir
maternidad o paternidad queda como indicio, no como hecho cerrado. No se inventa.
"""
import re

from app.contenido import acotar
from app.perfil_redes import _agregar, _n

# Primera persona o ficha: la persona habla de SUS hijos.
_YO_HIJOS = re.compile(
    r"\b("
    r"soy (?:mama|papa|madre)(?:\b| de)|"
    r"soy padre de\b|"
    r"(?:mama|papa|madre|padre) de\b|"
    r"(?:madre|padre|mama|papa) primeriz[oa]|"
    r"boy mom|girl mom|mom of|dad of|"
    r"tengo (?:un |una |dos |tres |cuatro |\d+ )?(?:hijo|hija|hijos|hijas|bebe|bebes)|"
    r"mis (?:hijos|hijas|bebes|peques|ninos|ninas)|"
    r"mi (?:hijo|hija|bebe|beba|nene|nena|nino|nina)|"
    r"nuestr[oa]s? (?:hijo|hija|hijos|hijas|bebe|bebes)|"
    r"con mi(?:s)? (?:hijo|hija|hijos|hijas|bebe)|"
    r"estoy embarazada|estamos embarazad|"
    r"vamos a ser (?:mama|papa|padres)|"
    r"esperando (?:a |un |una )?(?:bebe|hijo|hija|nuestro bebe)"
    r")\b"
)
_FICHA_HIJO = re.compile(
    r"\b(hijo|hija)s?\s*:\s*[A-ZÁÉÍÓÚÑa-záéíóúñ]"
)
_FUERTE = re.compile(
    r"\b(mi hijo|mi hija|mis hijos|mis hijas|mama de|papa de|"
    r"soy mama|soy madre|hijo:|hija:|mi bebe|con mi hija|con mi hijo)\b"
)
# No es declaración de hijos propios.
_NO_PROPIO = re.compile(
    r"\b("
    r"su hijo|su hija|tus hijos|tus hijas|sus hijos|sus hijas|"
    r"mi mama|mi papa|mi madre|mi padre|mis padres|"
    r"el hijo de|la hija de|hijo de dios|"
    r"familias? clientes|apoyo a las familias"
    r")\b"
)
_FESTIVO = re.compile(
    r"\b(dia de (?:la |las )?madres|dia del padre|mother'?s day|father'?s day)\b"
)
# Tema de maternidad/paternidad en un contenido compartido (indicio, no certeza).
_MATERNIDAD = re.compile(
    r"\b("
    r"maternidad|paternidad|crianza|parenting|lactancia|"
    r"ser mama|ser papa|ser madre|ser padre|"
    r"primeriza|primerizo|embarazo|gestacion|"
    r"dia de (?:la |las )?madres|dia del padre"
    r")\b"
)
_MARCA_SHARE = re.compile(
    r"(?:^|\n)\s*(?:reposte[oó]|reposted|comparti[oó]|shared a|"
    r"una publicaci[oó]n de)\b",
    re.I,
)


def _frase_util(texto, limite=180):
    t = re.sub(r"\s+", " ", str(texto or "")).strip(" .")
    return acotar(t, limite) if t else ""


def _texto_post(post):
    post = post or {}
    partes = [post.get("texto") or ""]
    for alt in post.get("alts") or []:
        if isinstance(alt, str) and alt.strip():
            partes.append(alt)
    return " ".join(partes)


def _es_compartida(post):
    tipo = (post.get("tipo") or "publicacion").lower()
    return tipo in {"compartida", "repost", "reposteada", "compartido"}


def _cabecera_propia(texto):
    """En un share, solo lo que la persona escribió antes de la marca de repost."""
    t = str(texto or "")
    marca = _MARCA_SHARE.search(t)
    if not marca:
        return ""
    return t[:marca.start()]


def _es_declaracion(n):
    if not n:
        return False
    if _FICHA_HIJO.search(n):
        return True
    if not _YO_HIJOS.search(n):
        return False
    if _NO_PROPIO.search(n) and not _FUERTE.search(n):
        return False
    return True


def _es_solo_ajeno(n):
    return bool(n and _NO_PROPIO.search(n) and not _YO_HIJOS.search(n))


def analizar(info, posts=None):
    """Revisa ficha, bio, captions, alts y shares.

    -> {certeza: alta|media|indicio|'', resumen, evidencias}
    alta: lo dijo en bio/ficha o en un caption propio.
    media: lo escribió al compartir (comentario propio del share).
    indicio: compartió maternidad/paternidad sin declararse madre/padre.
    """
    evidencias = []
    vistos = set()

    def anotar(nivel, origen, frase):
        frase = _frase_util(frase)
        if not frase:
            return
        clave = (_n(frase), origen)
        if clave in vistos:
            return
        vistos.add(clave)
        evidencias.append({"certeza": nivel, "origen": origen, "frase": frase})

    info = info or {}
    for origen, texto in (
        ("ficha", info.get("familia") or ""),
        ("bio", info.get("bio") or ""),
        ("titular", info.get("titular") or ""),
        ("acerca", info.get("acerca") or ""),
        ("presentacion", info.get("estado_civil") or ""),
    ):
        n = _n(texto)
        if _es_declaracion(n) and not _es_solo_ajeno(n):
            anotar("alta", origen, texto)

    for post in posts or []:
        bruto = _texto_post(post)
        n = _n(bruto)
        if not n:
            continue
        if _es_compartida(post):
            cabeza = _cabecera_propia(bruto)
            n_cab = _n(cabeza)
            if _es_declaracion(n_cab) and not _es_solo_ajeno(n_cab):
                anotar("media", "caption al compartir", cabeza)
            elif _MATERNIDAD.search(n) or _FESTIVO.search(n):
                anotar("indicio", "compartida", bruto)
            continue
        if _es_solo_ajeno(n):
            continue
        if _es_declaracion(n):
            origen = ("caption de foto"
                      if post.get("tiene_imagenes") or post.get("alts")
                      else "publicacion")
            anotar("alta", origen, bruto)

    orden = {"alta": 0, "media": 1, "indicio": 2}
    evidencias.sort(key=lambda e: (orden.get(e["certeza"], 9), e["origen"]))
    niveles = [e["certeza"] for e in evidencias]
    if "alta" in niveles:
        certeza = "alta"
    elif "media" in niveles:
        certeza = "media"
    elif "indicio" in niveles:
        certeza = "indicio"
    else:
        certeza = ""
    return {
        "certeza": certeza,
        "evidencias": evidencias,
        "resumen": _resumen(certeza, evidencias),
    }


def _resumen(certeza, evidencias):
    if not evidencias:
        return ""
    citas = "; ".join(f"{e['origen']}: «{e['frase']}»" for e in evidencias[:4])
    if certeza == "alta":
        return "Tiene hijos (dato declarado por la persona). " + citas
    if certeza == "media":
        return "Tiene hijos (lo escribió al compartir una publicación). " + citas
    return ("Indicio de hijos: compartió contenido de maternidad o paternidad, "
            "sin declararse madre o padre. " + citas)


def aplicar(info, posts=None):
    """Deja en la ficha el resultado del análisis de hijos, sin inventar."""
    info = dict(info or {})
    hallado = analizar(info, posts)
    info["hijos_certeza"] = hallado["certeza"]
    info["hijos_evidencias"] = hallado["evidencias"]
    if hallado["resumen"]:
        info["hijos"] = hallado["resumen"]
    elif "hijos" in info:
        info.pop("hijos", None)
    return info


def hechos_de(info):
    """Hechos para revisión: Hijos (certeza) o Indicio de hijos."""
    hechos = []
    resumen = (info or {}).get("hijos") or ""
    certeza = (info or {}).get("hijos_certeza") or ""
    if not resumen:
        return hechos
    if certeza in {"alta", "media"}:
        _agregar(hechos, "Hijos", resumen)
    else:
        _agregar(hechos, "Indicio de hijos", resumen)
    return hechos
