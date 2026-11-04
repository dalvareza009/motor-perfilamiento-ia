"""Extracción de conocimiento desde markdown (páginas y PDFs). Lógica pura: sin red ni BD.
Pensado para la estructura de globalseguroscolombia.com (Elementor):
  - encabezados H1-H3 inician un fragmento; H4+ se pliegan dentro ("Cobertura: ...; Lugar: ...")
  - preguntas frecuentes en negrita (**¿...?**) seguidas de su respuesta
  - listas con viñetas "- **Global**Producto" + descripción (página /productos/)
  - se descartan menús, avisos temporales, formularios, pies de página y botones (CTA)
"""
import re
import unicodedata
from urllib.parse import unquote, urlparse

MAX_CHARS = 1200
MIN_CHARS = 60
SUB = "\x00SUB:"

BOILERPLATE_TITULOS = ["contactanos", "servicio en linea", "llamanos", "siguenos", "recaudo (pago inicial)",
                       "copyright", "politica de privacidad", "cookies", "mapa del sitio", "iniciar sesion"]
BOILERPLATE_TEXTO = ["sismo", "temporalmente cerradas", "acepto el tratamiento de datos",
                     "todos los derechos reservados", "cookies", "suscrib", "newsletter"]
# Secciones de comparación que solo tienen sentido dentro de cada producto (ya están plegadas en él)
GENERICOS = {"cobertura", "lugar", "periodos de cobertura", "suma asegurada", "edad maxima de ingreso",
             "clausulado y tarifas", "coberturas adicionales", "tramite de pago"}
CTA = ["¡lo quiero", "lo quiero!", "ver clausulado", "ver tarifas", "ver anexo", "conocer mas", "conoce mas",
       "mas informacion", "consulta el centro de ayuda", "pagar aqui", "agenda tu cita"]

HEAD = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
BOLD_LINEA = re.compile(r"^\s*\*\*(.+?)\*\*\s*$")
VINETA = re.compile(r"^\s*[-*]\s+(\S.*)$")
PREFIJAR = re.compile(r"^(plan|opcion|nivel)\s*\d+")


def _n(texto):
    t = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


CTA_N = tuple(_n(c) for c in CTA)


# ------------------------------------------------------------------ limpieza
def limpiar_texto(t):
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)            # imágenes (primero: pueden ir dentro de enlaces)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)         # [texto](url) -> texto
    t = re.sub(r"<[^>]+>", "", t)                          # etiquetas HTML y <autoenlaces>
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"\*\*|__", "", t)
    return re.sub(r"[ \t\u00a0]+", " ", t).strip()


def _lineas_limpias(lineas):
    salida, vistos = [], set()
    for l in lineas:
        if l.startswith(SUB):
            continue
        t = re.sub(r"^[-*•]\s+", "", limpiar_texto(l)).strip()
        if not t or re.match(r"^#\S*$", t) or _n(t).startswith(CTA_N):
            continue
        k = _n(t)
        if k not in vistos:
            vistos.add(k)
            salida.append(t)
    return salida


def limpiar(texto):
    return "\n".join(_lineas_limpias(texto.splitlines()))


# ------------------------------------------------------------------ troceado sin pérdida
def _partir_largo(linea):
    piezas, actual = [], ""
    for frase in re.split(r"(?<=[.;:])\s+", linea):
        while len(frase) > MAX_CHARS:
            corte = frase.rfind(" ", 0, MAX_CHARS)
            corte = corte if corte > 0 else MAX_CHARS
            if actual:
                piezas.append(actual)
                actual = ""
            piezas.append(frase[:corte])
            frase = frase[corte:].lstrip()
        if actual and len(actual) + 1 + len(frase) > MAX_CHARS:
            piezas.append(actual)
            actual = frase
        else:
            actual = f"{actual} {frase}".strip()
    if actual:
        piezas.append(actual)
    return piezas


def _trozos(lineas):
    trozos, actual = [], ""
    for l in lineas:
        for p in _partir_largo(l):
            if actual and len(actual) + 1 + len(p) > MAX_CHARS:
                trozos.append(actual)
                actual = p
            else:
                actual = f"{actual}\n{p}" if actual else p
    if actual:
        trozos.append(actual)
    return trozos


def _frag(titulo, contenido, categoria, grupo):
    return {"titulo": titulo, "contenido": contenido, "categoria": categoria, "grupo": grupo}


def _en_trozos(titulo, lineas, categoria, grupo, minimo=MIN_CHARS):
    salida = []
    for i, trozo in enumerate(_trozos(lineas), 1):
        if len(trozo) >= minimo:
            salida.append(_frag(titulo[:150] if i == 1 else f"{titulo[:140]} ({i})", trozo, categoria, grupo))
    return salida


def _unicos(frags):
    vistos, cuenta, salida = set(), {}, []
    for f in frags:
        if (f["titulo"], f["contenido"]) in vistos:
            continue
        vistos.add((f["titulo"], f["contenido"]))
        n = cuenta.get(f["titulo"], 0) + 1
        cuenta[f["titulo"]] = n
        salida.append(f if n == 1 else {**f, "titulo": f"{f['titulo'][:140]} [{n}]"})
    return salida


# ------------------------------------------------------------------ páginas
def categoria(titulo, cuerpo=""):
    """Sugerencia por el TÍTULO; el humano la revisa. 'Regla de negocio' nunca se sugiere desde la web."""
    t = _n(titulo)
    if "exclusi" in t:
        return "Exclusión"
    if any(k in t for k in ("cobertura", "amparo", "indemniz")):
        return "Cobertura"
    if any(k in t for k in ("beneficio", "ventaja")):
        return "Beneficio"
    if titulo.strip().startswith("¿") or t.startswith("preguntas frecuentes") or "faq" in t:
        return "Pregunta frecuente"
    return "Producto"


def _unidades(markdown):
    unidades, actual, grupo = [], None, ""
    for linea in markdown.splitlines():
        m = HEAD.match(linea)
        if m:
            nivel, titulo = len(m.group(1)), limpiar_texto(m.group(2)).strip("# ").strip()
            if nivel <= 3:
                if nivel <= 2:
                    grupo = titulo
                actual = {"nivel": nivel, "titulo": titulo, "lineas": [], "grupo": grupo}
                unidades.append(actual)
                continue
            if actual is None:
                actual = {"nivel": 0, "titulo": "", "lineas": [], "grupo": ""}
                unidades.append(actual)
            actual["lineas"].append(SUB + titulo)
            continue
        if actual is None:
            actual = {"nivel": 0, "titulo": "", "lineas": [], "grupo": ""}
            unidades.append(actual)
        actual["lineas"].append(linea)
    return unidades


def _componer(lineas):
    """Pliega los subtítulos (H4+) en líneas 'Subtítulo: contenido'."""
    segs = [(None, [])]
    for l in lineas:
        if l.startswith(SUB):
            segs.append((l[len(SUB):], []))
        else:
            segs[-1][1].append(l)
    salida, vistos = [], set()
    for sub, ls in segs:
        limpias = _lineas_limpias(ls)
        if not limpias:
            continue
        for t in (limpias if sub is None else [f"{sub}: " + " ".join(limpias)]):
            if _n(t) not in vistos:
                vistos.add(_n(t))
                salida.append(t)
    return salida


def _extraer_faq(lineas):
    resto, pares, actual = [], [], None
    for l in lineas:
        m = BOLD_LINEA.match(l)
        if m and ("¿" in m.group(1) or m.group(1).rstrip().endswith("?")):
            actual = (limpiar_texto(m.group(1)), [])
            pares.append(actual)
        elif actual is not None:
            actual[1].append(l)
        else:
            resto.append(l)
    return resto, pares


def _items(lineas):
    """Viñetas con descripción (página /productos/). Solo si hay al menos 2 con texto propio."""
    items, actual = [], None
    for l in lineas:
        m = VINETA.match(l)
        if m:
            actual = [limpiar_texto(m.group(1)), []]
            items.append(actual)
        elif actual is not None and not l.startswith(SUB):
            actual[1].append(l)
    validos = [(t, _lineas_limpias(d)) for t, d in items if t]
    validos = [(t, d) for t, d in validos if len("\n".join(d)) >= MIN_CHARS]
    return validos if len(validos) >= 2 else []


def _es_boilerplate(titulo, cuerpo):
    return (any(b in _n(titulo) for b in BOILERPLATE_TITULOS)
            or any(b in _n(cuerpo[:300]) for b in BOILERPLATE_TEXTO))


def fragmentos_pagina(markdown):
    """-> (fragmentos, genericos_omitidos). Fragmento = {titulo, contenido, categoria, grupo}."""
    unidades = _unidades(markdown or "")
    hay_encabezados = any(u["nivel"] > 0 for u in unidades)
    frags, omitidos = [], 0
    for u in unidades:
        if u["nivel"] == 0 and hay_encabezados:      # lo previo al primer encabezado: menús y avisos
            continue
        titulo, grupo = u["titulo"] or "Descripción general", u["grupo"]
        if any(b in _n(titulo) for b in BOILERPLATE_TITULOS):
            continue

        resto, pares = _extraer_faq(u["lineas"])
        for q, ans in pares:
            lineas = _componer(ans)
            if lineas:
                frags += _en_trozos(q, lineas, "Pregunta frecuente", grupo, minimo=20)

        if u["nivel"] == 3 and _n(titulo) in GENERICOS:
            omitidos += 1
            continue

        items = _items(resto)
        if items:
            for t, d in items:
                frags += _en_trozos(t, d, "Producto", grupo)
            continue

        lineas = _componer(resto)
        if len("\n".join(lineas)) < MIN_CHARS or _es_boilerplate(titulo, "\n".join(lineas)):
            continue
        if u["nivel"] == 3 and PREFIJAR.match(_n(titulo)) and grupo and grupo != titulo:
            titulo = f"{grupo} › {titulo}"
        frags += _en_trozos(titulo, lineas, categoria(titulo), grupo)
    return _unicos(frags), omitidos


# ------------------------------------------------------------------ PDFs
def enlaces_pdf(markdown, incluir_tarifas=False):
    urls = re.findall(r"https?://[^\s)\]]+?\.pdf", markdown or "", flags=re.I)
    salida = []
    for u in urls:
        if u not in salida and (incluir_tarifas or "tarifa" not in _n(unquote(u))):
            salida.append(u)
    return salida


def nombre_pdf(url):
    base = unquote(urlparse(url).path.rsplit("/", 1)[-1])
    base = re.sub(r"\.pdf$", "", base, flags=re.I)
    return re.sub(r"\s+", " ", re.sub(r"[-_]+", " ", base)).strip()


def _es_encabezado_pdf(linea):
    s = linea.strip().strip("#*").strip()
    if not (5 <= len(s) <= 100) or s.endswith((".", ",", ";")):
        return False
    if re.match(r"(?i)^(art[ií]culo|cl[aá]usula|cap[ií]tulo|secci[oó]n|anexo)\s+\S+", s):
        return True
    letras = [c for c in s if c.isalpha()]
    return len(letras) >= 5 and all(c.isupper() for c in letras)


def fragmentos_pdf(markdown, nombre, max_fragmentos=120):
    """-> (fragmentos, truncado). Clausulado general; 'Exclusión' si el encabezado lo indica."""
    secciones, titulo, buf = [], nombre, []
    for linea in (markdown or "").splitlines():
        m = HEAD.match(linea)
        if m or _es_encabezado_pdf(linea):
            secciones.append((titulo, buf))
            titulo = limpiar_texto(m.group(2) if m else linea).strip("#* ").strip() or nombre
            buf = []
        else:
            buf.append(linea)
    secciones.append((titulo, buf))

    frags = []
    for tit, b in secciones:
        lineas = _lineas_limpias(b)
        if lineas:
            base = nombre if tit == nombre else f"{nombre}: {tit}"
            frags += _en_trozos(base, lineas, "Exclusión" if "exclusi" in _n(tit) else "Clausulado", nombre)
    frags = _unicos(frags)
    return frags[:max_fragmentos], len(frags) > max_fragmentos


# ------------------------------------------------------------------ familia de producto
FAMILIAS = [("vitalicia", "Seguro renta vitalicia"), ("renta", "Seguro renta voluntaria"),
            ("previsional", "Seguro previsional"), ("pension", "Seguro de pensión"),
            ("accidentes", "Seguro de accidentes personales"), ("educativ", "Seguro educativo"),
            ("vida", "Seguro de vida")]


def familia_por_grupo(grupo):
    g = _n(grupo)
    for clave, nombre in FAMILIAS:
        if clave in g:
            return nombre
    return None