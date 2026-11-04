"""Extracción y filtro de una página pública de LinkedIn. Lógica pura: sin navegador ni base de datos.

Si la página es un muro de acceso, no hay publicaciones. Si un texto habla de política
o religión, se descarta y no se convierte en interés. El salario NO es un tema
restringido: se detecta como señal de ingresos y se tiene en cuenta en el perfil.
"""
import re
import unicodedata
from html.parser import HTMLParser

from app.perfil_redes import cargar_autorizados, clasificar_url, es_muro_de_acceso

MIN_CHARS = 40
MAX_CHARS = 2000

SENSIBLES = (
    ("politica", re.compile(
        r"\b(politica|partido politico|voto por|elecciones|ideologia|campana electoral)\b")),
    ("religion", re.compile(
        r"\b(religion|iglesia|catolic|cristian|musulman|ateo|biblia|culto)\b")),
)

# tema, patrón ya sin tildes, producto del catálogo, razón que ve el revisor
REGLAS = (
    ("estudios", re.compile(r"\b(universidad|maestr|colegio|pregrado|posgrado|estudiante|estudie|estudio)\b"),
     "Seguro educativo", "La publicación pública menciona estudios."),
    ("hijos", re.compile(r"\b(mi hijo|mi hija|mis hijos|mis hijas)\b"),
     "Seguro educativo", "La publicación pública menciona hijos."),
    ("hijos", re.compile(r"\b(mi hijo|mi hija|mis hijos|mis hijas)\b"),
     "Seguro de vida", "La publicación pública menciona hijos."),
    ("familia", re.compile(r"\b(esposo|esposa|mi pareja|mi familia|casado|casada|estado civil)\b"),
     "Seguro de vida", "La publicación pública menciona familia o estado civil."),
    ("jubilacion", re.compile(r"\b(jubil|pension|me retiro|retiro laboral)\b"),
     "Seguro de pensión", "La publicación pública menciona jubilación o pensión."),
    ("jubilacion", re.compile(r"\b(jubil|pension|me retiro|retiro laboral)\b"),
     "Seguro renta vitalicia", "La publicación pública menciona jubilación o pensión."),
    ("accidentes", re.compile(r"\b(ciclismo|moto|deporte|accidente)\b"),
     "Seguro de accidentes personales", "La publicación pública menciona una actividad con riesgo de accidente."),
    ("ahorro", re.compile(r"\b(ahorro|inversion)\b"),
     "Seguro renta voluntaria", "La publicación pública menciona ahorro o inversión."),
)


def _n(texto):
    t = unicodedata.normalize("NFD", str(texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


def _limpiar(texto):
    return re.sub(r"\s+", " ", str(texto or "")).strip()


def motivo_sensible(texto):
    """-> 'politica' | 'religion' | ''."""
    n = _n(texto)
    for nombre, patron in SENSIBLES:
        if patron.search(n):
            return nombre
    return ""


SALARIO = re.compile(
    r"\b(salario|sueldo|ingresos|honorarios|remuneracion|compensacion|salary|compensation|"
    r"aumento salarial|me pagaron|mi paga)\b")


def menciona_salario(texto):
    """El salario cuenta como señal de ingresos del perfil (no es restricción)."""
    return bool(SALARIO.search(_n(texto)))


def _urn_de_publicacion(urn):
    u = (urn or "").lower()
    return "activity" in u or "ugcpost" in u or ":share:" in u


class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.posts = []
        self.texto = []
        self._pila = []
        self._profundidad = 0
        self._ignorar = 0

    def handle_starttag(self, tag, attrs):
        self._profundidad += 1
        if tag in {"script", "style", "noscript"}:
            self._ignorar += 1
            return
        if self._ignorar:
            return
        ad = {k: (v or "") for k, v in attrs}
        urn = ad.get("data-urn", "")
        if tag in {"div", "li", "article"} and _urn_de_publicacion(urn):
            self._pila.append({"urn": urn, "partes": [], "profundidad": self._profundidad,
                               "tiempo": ad.get("datetime", ""), "en_tiempo": False})
        if self._pila and tag == "time":
            self._pila[-1]["en_tiempo"] = True
            if ad.get("datetime") and not self._pila[-1]["tiempo"]:
                self._pila[-1]["tiempo"] = ad["datetime"]

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self._ignorar:
            self._ignorar -= 1
        elif not self._ignorar and self._pila and tag == "time":
            self._pila[-1]["en_tiempo"] = False
        if not self._ignorar and self._pila and self._profundidad == self._pila[-1]["profundidad"]:
            post = self._pila.pop()
            texto = _limpiar(" ".join(post["partes"]))
            if len(texto) >= MIN_CHARS:
                self.posts.append({
                    "urn": post["urn"],
                    "texto": texto[:MAX_CHARS],
                    "tiempo": _limpiar(post["tiempo"])[:80],
                })
        self._profundidad = max(0, self._profundidad - 1)

    def handle_data(self, data):
        if self._ignorar or not data.strip():
            return
        self.texto.append(data)
        if not self._pila:
            return
        actual = self._pila[-1]
        if actual["en_tiempo"] and not actual["tiempo"]:
            actual["tiempo"] = data.strip()
        else:
            actual["partes"].append(data)


def pagina_es_muro(html, url_final=""):
    """True si LinkedIn muestra inicio de sesión en lugar del perfil."""
    final = (url_final or "").lower()
    if any(t in final for t in ("/login", "/signup", "/checkpoint", "authwall")):
        return True
    bajo = (html or "").lower()
    if "authwall" in bajo and "urn:li:activity" not in bajo and "urn:li:ugcpost" not in bajo:
        return True
    parser = _Extractor()
    try:
        parser.feed(html or "")
    except Exception:
        return True
    return es_muro_de_acceso(_limpiar(" ".join(parser.texto)))


def extraer_publicaciones(html, max_posts=10):
    """-> [{urn, texto, tiempo}]. Vacío si la página es un muro de acceso."""
    if pagina_es_muro(html):
        return []
    parser = _Extractor()
    try:
        parser.feed(html or "")
    except Exception:
        return []
    vistos, salida = set(), []
    for post in parser.posts:
        clave = _n(post["texto"])
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append(post)
        if len(salida) >= max_posts:
            break
    return salida


def intereses_de_texto(texto):
    """Temas y producto que el texto dice. Vacío si el texto es sensible o no encaja con ninguno."""
    if motivo_sensible(texto):
        return []
    n = _n(texto)
    if len(n) < MIN_CHARS:
        return []
    vistos, salida = set(), []
    for tema, patron, producto, razon in REGLAS:
        if not patron.search(n):
            continue
        clave = (tema, producto)
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append({"tema": tema, "producto": producto, "razon": razon})
    return salida


def evaluar_publicacion(texto):
    """-> {omitida, motivo, intereses, salario}.

    Solo política/religión omiten. El salario se reporta aparte como señal de
    ingresos: la publicación se conserva y puede apoyar otros temas.
    """
    motivo = motivo_sensible(texto)
    if motivo:
        return {"omitida": True, "motivo": motivo, "intereses": [], "salario": False}
    return {"omitida": False, "motivo": "", "intereses": intereses_de_texto(texto),
            "salario": menciona_salario(texto)}


def persona_de_url(url, personas):
    """La persona autorizada dueña de esa URL pública de LinkedIn, o None.

    Una URL de actividad (/recent-activity/) no es el perfil público y no se lee.
    """
    clasificada = clasificar_url(url)
    if not clasificada or clasificada[0] != "linkedin":
        return None
    _red, limpia = clasificada
    for persona in personas or []:
        for entrada in persona.get("urls") or []:
            if entrada.get("red") == "linkedin" and entrada.get("url") == limpia:
                return {**persona, "url": limpia}
    return None


def personas_linkedin(lista, nombre=""):
    """-> (personas con al menos un LinkedIn autorizado, avisos)."""
    personas, avisos = cargar_autorizados(lista)
    pedidas = []
    for persona in personas:
        urls = [u for u in persona["urls"] if u["red"] == "linkedin"]
        if not urls:
            continue
        if nombre and persona["nombre"].lower() != nombre.strip().lower():
            continue
        pedidas.append({**persona, "urls": urls})
    return pedidas, avisos
