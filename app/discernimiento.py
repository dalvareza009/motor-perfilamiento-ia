"""Qué revisar en TODA red (LinkedIn, Facebook, Instagram, X, Substack, Reddit).

En cada perfil se busca, si está dicho o se ve:
- a quién sigue y qué le interesa en la vida
- publicaciones y reposts relevantes para acercarnos
- estado civil, hijos, escolaridad, empresa donde trabaja, dónde estudió
- rango salarial solo si la persona lo publica (para el asesor; no va al mensaje)

No entra el ruido (memes, clima, «feliz viernes», karma, política, religión).
"""
import re
import unicodedata

from app.gustos import clasificar as clasificar_gusto, producto_de_gusto
from app.linkedin_texto import intereses_de_texto, menciona_salario, motivo_sensible
from app.tipo_dato import eje_ficha

# Por qué se queda un dato. El revisor y el agente usan las mismas claves.
PARAMETROS = (
    "a_quien_sigue",
    "intereses_de_vida",
    "publicaciones_relevantes",
    "reposts_relevantes",
    "trabajo_actual",
    "empresa",
    "experiencia_laboral",
    "estudios_formales",
    "escolaridad",
    "cursos_certificacion",
    "familia_hijos",
    "estado_civil",
    "edad",
    "ubicacion",
    "rango_salarial",
    "ahorro_inversion",
    "jubilacion",
    "riesgo_accidente",
    "vivienda",
    "emprendimiento",
    "salud_bienestar",
    "gusto_con_producto",
)

_EJE_UTIL = {
    "Trabajo": "trabajo_actual",
    "Experiencia": "experiencia_laboral",
    "Estudios": "estudios_formales",
    "Cursos": "cursos_certificacion",
    "Familia": "familia_hijos",
}

_RUIDO = re.compile(
    r"^(ok|lol|lmao|jajaja+|jsjsj+|same|this|nice|wow|based|cringe|"
    r"feliz (?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)|"
    r"happy (?:friday|monday)|buen (?:dia|finde)|gm\b|gn\b|"
    r"clima|nublado|lloviendo|hace calor)\b",
    re.I,
)
_META_RED = re.compile(
    r"\b(karma|upvote|downvote|awards?|redditor|joined reddit|"
    r"cake day|moderator|subreddit|follow me|suscribete|"
    r"like and share|link in bio)\b",
    re.I,
)

# Comunidades que sí dicen algo del riesgo o del momento de vida.
SUBREDDITS_UTIL = {
    "personalfinance": "ahorro_inversion",
    "povertyfinance": "ahorro_inversion",
    "investing": "ahorro_inversion",
    "stocks": "ahorro_inversion",
    "financialindependence": "ahorro_inversion",
    "colombia": "ubicacion",
    "medellin": "ubicacion",
    "bogota": "ubicacion",
    "cali": "ubicacion",
    "barranquilla": "ubicacion",
    "parenting": "familia_hijos",
    "daddit": "familia_hijos",
    "mommit": "familia_hijos",
    "beyondthebump": "familia_hijos",
    "newparents": "familia_hijos",
    "motorcycles": "riesgo_accidente",
    "motorcycle": "riesgo_accidente",
    "cycling": "riesgo_accidente",
    "bicycling": "riesgo_accidente",
    "running": "riesgo_accidente",
    "jobs": "trabajo_actual",
    "careerguidance": "trabajo_actual",
    "cscareerquestions": "trabajo_actual",
    "gradschool": "estudios_formales",
    "college": "estudios_formales",
    "university": "estudios_formales",
    "realestate": "vivienda",
    "homeowners": "vivienda",
    "firsttimehomebuyer": "vivienda",
    "entrepreneur": "emprendimiento",
    "smallbusiness": "emprendimiento",
    "retirement": "jubilacion",
    "personalfinancecolombia": "ahorro_inversion",
}

SUBREDDITS_RUIDO = {
    "funny", "memes", "dankmemes", "me_irl", "pics", "aww", "gifs", "videos",
    "mildlyinteresting", "interestingasfuck", "shitposting", "adviceanimals",
    "wholesomememes", "memeeconomy", "okbuddyretard", "circlejerk",
}


def _n(texto):
    t = unicodedata.normalize("NFD", str(texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


def _mezcla(post):
    post = post or {}
    partes = [
        post.get("texto"), post.get("texto_imagen"), post.get("descripcion_imagen"),
        post.get("autor"), post.get("subreddit"),
    ]
    for a in post.get("alts") or []:
        if isinstance(a, str):
            partes.append(a)
    return " ".join(p for p in partes if p)


def evaluar(texto, subreddit=""):
    """-> {sirve, parametros, productos, motivo}."""
    n = _n(texto)
    sub = _n(subreddit).replace("r/", "")
    if motivo_sensible(texto):
        return {"sirve": False, "parametros": [], "productos": [],
                "motivo": "tema_sensible"}
    if sub in SUBREDDITS_RUIDO and len(n) < 80:
        return {"sirve": False, "parametros": [], "productos": [],
                "motivo": "comunidad_sin_senal"}
    if not n or len(n) < 12:
        if sub in SUBREDDITS_UTIL:
            clave = SUBREDDITS_UTIL[sub]
            return {"sirve": True, "parametros": [clave], "productos": [],
                    "motivo": clave}
        return {"sirve": False, "parametros": [], "productos": [],
                "motivo": "sin_texto"}
    if _RUIDO.search(n) and len(n) < 80:
        return {"sirve": False, "parametros": [], "productos": [],
                "motivo": "ruido"}
    if _META_RED.search(n) and len(n) < 80:
        return {"sirve": False, "parametros": [], "productos": [],
                "motivo": "meta_red"}

    parametros, productos = [], []

    def marcar(clave, producto=""):
        if clave and clave not in parametros:
            parametros.append(clave)
        if producto and producto not in productos:
            productos.append(producto)

    if sub in SUBREDDITS_UTIL:
        marcar(SUBREDDITS_UTIL[sub])
    eje = eje_ficha(texto)
    if eje in _EJE_UTIL:
        marcar(_EJE_UTIL[eje])
    from app.perfil_redes import (ESTADO_CIVIL, FAMILIA, UBICACION, categorias_oracion)
    cats = categorias_oracion(texto)
    if "Edad" in cats:
        marcar("edad")
    if "Estado civil" in cats or ESTADO_CIVIL.search(n):
        marcar("estado_civil")
    if "Familia" in cats or FAMILIA.search(n):
        marcar("familia_hijos")
    if "Ubicacion" in cats or UBICACION.search(n):
        marcar("ubicacion")
    if menciona_salario(texto):
        marcar("rango_salarial")
    if eje == "Trabajo" and re.search(r"\b(en|at|@)\b", n):
        marcar("empresa")
    if eje == "Estudios":
        marcar("escolaridad")
    for interes in intereses_de_texto(texto):
        tema = interes.get("tema") or ""
        if tema == "hijos":
            marcar("familia_hijos", interes.get("producto"))
        elif tema == "estudios":
            marcar("estudios_formales", interes.get("producto"))
        elif tema == "familia":
            marcar("familia_hijos", interes.get("producto"))
        elif tema == "jubilacion":
            marcar("jubilacion", interes.get("producto"))
        elif tema == "accidentes":
            marcar("riesgo_accidente", interes.get("producto"))
        elif tema == "ahorro":
            marcar("ahorro_inversion", interes.get("producto"))
        else:
            marcar(tema, interes.get("producto"))
    for gusto in clasificar_gusto(texto):
        marcar("intereses_de_vida")
        producto = producto_de_gusto(gusto)
        if producto:
            marcar("gusto_con_producto", producto)
    if not parametros:
        return {"sirve": False, "parametros": [], "productos": [],
                "motivo": "sin_senal_comercial"}
    return {"sirve": True, "parametros": parametros, "productos": productos,
            "motivo": parametros[0]}


def sirve_post(post):
    sub = post.get("subreddit") or ""
    return evaluar(_mezcla(post), subreddit=sub)["sirve"]


def filtrar_posts(posts):
    """Deja solo piezas que aportan al perfil de seguro."""
    return [p for p in (posts or []) if sirve_post(p)]


def gusto_comercial(categoria):
    return bool(producto_de_gusto(categoria))


# Estas categorías no se aprueban solas: siguen, gustos, publicaciones, cursos, salario.
_NO_AUTO = {
    "producto sugerido", "sigue a", "gusto", "repost", "seguidor",
    "paginas seguidas", "interacciones", "interes", "publicacion",
    "mensaje", "comentario", "reaccion", "resumen de contenido",
    "otra red", "ingresos", "contacto", "logros", "cursos",
}
_VAGAS = {"", "descripcion", "informacion", "situacion actual"}
_ORIGEN = re.compile(
    r"\b(soy de|naci en|nacido en|nacida en|originari[oa] de|natural de|procedo de)\b"
)
_LUGAR = re.compile(
    r"^[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ .'-]{1,40}"
    r"(?:,\s*[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ .'-]{1,40}){1,3}$"
)
_TRABAJO_REAL = re.compile(
    r"\b(trabajo (?:en|como|de)|trabaje (?:en|como|de)|trabaja (?:en|como|de)|"
    r"me dedico|experiencia laboral|experiencia (?:en|como)|cargo de|"
    r"estoy emplead|soy emplead|soy independiente|trabajo independiente|"
    r"soy autonom|estoy pensionad|soy pensionad|estoy jubilad|soy jubilad|"
    r"estoy desemplead|soy desemplead|actualmente trabajo|estoy trabajando)\b"
)
_BUSCA_EMPLEO = re.compile(r"\b(busco empleo|buscando empleo)\b")
_EN_EQUIPO = re.compile(r"\btrabajo en equipo\b")


def _senales_ficha(texto):
    """Trabajo real, estudios, estado civil, origen, dónde vive o edad. Nada más."""
    from app.linkedin_texto import menciona_salario, motivo_sensible
    from app.perfil_redes import (
        CIUDAD, ESTADO_ACADEMICO, ESTADO_CIVIL, ESTADO_LABORAL, TRABAJO_CARGO,
        UBICACION, _VIAJE, edad_de_frase,
    )
    from app.tipo_dato import eje_ficha

    crudo = str(texto or "").strip()
    n = _n(crudo)
    if not n or motivo_sensible(crudo) or menciona_salario(crudo):
        return set()
    if _VIAJE.search(n):
        return set()
    senales = set()
    if edad_de_frase(crudo):
        senales.add("Edad")
    if ESTADO_CIVIL.search(n):
        senales.add("Estado civil")
    if _ORIGEN.search(n):
        senales.add("Origen")
    elif UBICACION.search(n) or CIUDAD.match(crudo) or _LUGAR.match(crudo):
        senales.add("Ubicacion")
    eje = eje_ficha(crudo)
    if eje == "Estudios" or (ESTADO_ACADEMICO.search(n) and eje != "Cursos"):
        senales.add("Estudios" if eje == "Estudios" else "Estado academico")
    busca = bool(_BUSCA_EMPLEO.search(n)) and not TRABAJO_CARGO.search(n)
    en_equipo = bool(_EN_EQUIPO.search(n)) and not TRABAJO_CARGO.search(n)
    if not busca and not en_equipo and (
            TRABAJO_CARGO.search(n) or _TRABAJO_REAL.search(n) or ESTADO_LABORAL.search(n)):
        if eje == "Experiencia":
            senales.add("Experiencia")
        elif ESTADO_LABORAL.search(n) and eje not in ("Trabajo", "Experiencia"):
            senales.add("Estado laboral")
        else:
            senales.add("Trabajo")
    return senales


def ficha_necesaria(categoria, contenido):
    """Categoría con la que se puede aprobar solo. Vacío si hace falta una persona."""
    if _n(categoria) in _NO_AUTO:
        return ""
    senales = _senales_ficha(contenido)
    if not senales:
        return ""
    if categoria in senales:
        return categoria
    if _n(categoria) in _VAGAS and len(senales) == 1:
        return next(iter(senales))
    return ""
