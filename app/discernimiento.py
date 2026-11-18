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
