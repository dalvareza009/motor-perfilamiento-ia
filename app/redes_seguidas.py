"""Seguidores, cuentas que sigue e intereses visibles en cada red.

El scrape baja la lista (el contenedor con scroll, no la ventana) hasta que
deja de aparecer gente nueva o llega al tope. Cada nombre se guarda como un
hecho aparte para revisarlo en la pestaña «Seguidores e intereses».
"""
import re
import time
import unicodedata
from collections import Counter

CATEGORIAS_RED = (
    "Seguidor",
    "Sigue a",
    "Repost",
)

RUIDO = {
    "seguir", "siguiendo", "follow", "following", "followers", "seguidores",
    "seguidos", "mensaje", "mensajes", "conectar", "connect", "ver más",
    "see more", "sugerencias", "suggestions", "pages", "paginas", "empresas",
    "grupos", "escuelas", "newsletters", "influencers", "top voices",
    "companies", "schools", "groups", "intereses", "interests", "me gusta",
    "likes", "personas", "people", "inicio", "home", "perfil", "profile",
    "explorar", "explore", "notificaciones", "notifications", "cerrar",
    "close", "buscar", "search", "ver todo", "see all", "amigos", "friends",
}

_MENCION = re.compile(r"@([A-Za-z0-9_.]{2,30})")
_RESPUESTA = re.compile(
    r"(?:en respuesta a|replying to)\s+@?([A-Za-z0-9_.]+)", re.I)
TOPE_LISTA = 400
_TOPE_INTERACCION = 40


def tope_publicaciones(max_posts, defecto=10):
    """El número que pide la interfaz es el total por persona (1 a 10), no un cupo por tipo."""
    try:
        n = int(max_posts)
    except (TypeError, ValueError):
        n = defecto
    return min(10, max(1, n))


def elegir_publicaciones(publicaciones, max_posts, grupo_de=None, es_catalogo=None):
    """Hasta max_posts en total. Primero las que encajan con el catálogo; el resto se reparte entre tipos."""
    n = tope_publicaciones(max_posts)
    posts = list(publicaciones or [])
    if not posts or n < 1:
        return []
    es_catalogo = es_catalogo or (lambda _p: False)
    grupo_de = grupo_de or (lambda p: p.get("tipo") or "publicacion")
    usados = set()
    elegidas = []

    def tomar(post):
        clave = id(post)
        if clave in usados or len(elegidas) >= n:
            return False
        usados.add(clave)
        elegidas.append(post)
        return True

    for post in posts:
        if es_catalogo(post):
            tomar(post)
            if len(elegidas) >= n:
                return elegidas

    grupos = {}
    for post in posts:
        if id(post) in usados:
            continue
        grupos.setdefault(grupo_de(post), []).append(post)

    while len(elegidas) < n:
        avance = False
        for cola in grupos.values():
            if not cola:
                continue
            if tomar(cola.pop(0)):
                avance = True
            if len(elegidas) >= n:
                return elegidas
        if not avance:
            break
    return elegidas


def _n(texto):
    t = unicodedata.normalize("NFD", str(texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


def limpiar_nombre(texto):
    t = re.sub(r"\s+", " ", str(texto or "")).strip(" ·|-@")
    t = t.split("\n")[0].strip()
    if t.startswith("@"):
        t = t[1:]
    if len(t) < 2 or len(t) > 80:
        return ""
    if _n(t) in RUIDO:
        return ""
    if re.fullmatch(r"[\d.,\s]+", t):
        return ""
    if re.match(r"^(https?:|www\.)", t, re.I):
        return ""
    return t


def handle_de_url(url, red=""):
    u = str(url or "").rstrip("/")
    if red == "x" or "x.com/" in u or "twitter.com/" in u:
        m = re.search(r"(?:x|twitter)\.com/([^/?#]+)", u, re.I)
        return (m.group(1) if m else "")
    if red == "instagram" or "instagram.com/" in u:
        m = re.search(r"instagram\.com/([^/?#]+)", u, re.I)
        h = m.group(1) if m else ""
        return "" if h.lower() in ("p", "reel", "reels", "stories", "explore") else h
    return ""


def _es_dueno(nombre, dueno):
    a, b = _n(nombre), _n(dueno)
    if not a or not b:
        return False
    return a == b or a in b.split() or b in a


def limpiar_nombres(crudos, excluir=(), tope=TOPE_LISTA):
    vistos, salida = set(), []
    vetados = {_n(x) for x in excluir if x}
    for crudo in crudos or []:
        nombre = limpiar_nombre(crudo)
        clave = _n(nombre)
        if not nombre or clave in vistos or clave in vetados:
            continue
        vistos.add(clave)
        salida.append(nombre)
        if len(salida) >= tope:
            break
    return salida


def objetivos_de_post(post, dueno=""):
    post = post or {}
    tipo = (post.get("tipo") or "").lower()
    nombres = []
    autor = limpiar_nombre(post.get("autor") or "")
    if tipo == "compartida" and autor and not _es_dueno(autor, dueno):
        nombres.append(autor)
    texto = " ".join(p for p in (
        post.get("contexto_social"), post.get("social"), post.get("texto")) if p)
    for hallado in _RESPUESTA.findall(texto):
        nombres.append(hallado)
    for hallado in _MENCION.findall(texto):
        nombres.append(hallado)
    if tipo == "respuesta" and autor and not _es_dueno(autor, dueno):
        nombres.append(autor)
    return limpiar_nombres(nombres, excluir=(dueno,), tope=30)


def rankear_interacciones(posts, dueno="", tope=_TOPE_INTERACCION):
    cuenta = Counter()
    visibles = {}
    for post in posts or []:
        for nombre in objetivos_de_post(post, dueno=dueno):
            clave = _n(nombre)
            cuenta[clave] += 1
            visibles.setdefault(clave, nombre)
    return [(visibles[k], n) for k, n in cuenta.most_common(tope)]


def rankear_reposts(posts, dueno="", tope=_TOPE_INTERACCION):
    """Solo cuentas o páginas de las que esta persona hizo repost o compartió."""
    cuenta = Counter()
    visibles = {}
    for post in posts or []:
        if (post.get("tipo") or "").lower() != "compartida":
            continue
        autor = limpiar_nombre(post.get("autor") or "")
        if not autor or _es_dueno(autor, dueno):
            href = post.get("url_publicacion") or ""
            autor = limpiar_nombre(handle_de_url(href, "x") or handle_de_url(href, "instagram"))
        if not autor or _es_dueno(autor, dueno):
            menciones = _MENCION.findall(post.get("texto") or "")
            autor = limpiar_nombre(menciones[0]) if menciones else ""
        if not autor or _es_dueno(autor, dueno):
            continue
        clave = _n(autor)
        cuenta[clave] += 1
        visibles.setdefault(clave, autor)
    return [(visibles[k], n) for k, n in cuenta.most_common(tope)]


def formatear_seguidas(nombres):
    if not nombres:
        return ""
    return "Páginas o cuentas seguidas: " + ", ".join(nombres[:20])


def formatear_interacciones(ranking):
    if not ranking:
        return ""
    partes = [f"{nombre} ({n})" for nombre, n in ranking[:12]]
    return "Más interacción con: " + ", ".join(partes)


SCRIPT_SCROLL_LISTA = """
const dialog = document.querySelector('[role="dialog"]');
const roots = [];
if (dialog) {
    const boxes = [...dialog.querySelectorAll('div')].filter(d => d.scrollHeight > d.clientHeight + 40);
    boxes.sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight));
    if (boxes[0]) roots.push(boxes[0]);
    roots.push(dialog);
}
roots.push(document.querySelector('[data-testid="primaryColumn"]'));
roots.push(document.querySelector('main'));
roots.push(document.scrollingElement);
const el = roots.filter(Boolean).find(n => n.scrollHeight > n.clientHeight + 20)
    || document.scrollingElement;
if (!el) return 0;
el.scrollTop = el.scrollHeight;
window.scrollBy(0, 1800);
return el.scrollHeight || document.body.scrollHeight || 0;
"""

SCRIPT_X_CELDAS = """
return [...document.querySelectorAll('[data-testid="UserCell"], [data-testid="cellInnerDiv"]')].map(c => {
    const name = ((c.querySelector('[data-testid="UserName"]') || {}).innerText || '').split('\\n')[0];
    const user = [...c.querySelectorAll('a[href^="/"]')]
        .map(a => (a.getAttribute('href') || '').replace(/^\\//,'').split('/')[0])
        .find(h => /^[A-Za-z0-9_]{2,15}$/.test(h)
            && !['home','explore','search','i','settings','compose'].includes(h.toLowerCase()));
    return name || user || '';
});
"""

SCRIPT_LINKEDIN_INTERESES = """
const root = document.querySelector('main') || document.body;
return [...root.querySelectorAll(
    'a[href*="/company/"], a[href*="/school/"], a[href*="/groups/"], a[href*="/showcase/"], a[href*="/newsletters/"], a[href*="/in/"]'
)].map(a => ((a.innerText || '').split('\\n')[0] || '').trim());
"""

SCRIPT_LINKEDIN_PERSONAS = """
const root = document.querySelector('[role="dialog"]') || document.querySelector('main') || document.body;
return [...root.querySelectorAll('a[href*="/in/"]')].map(a => {
    const t = ((a.innerText || '').split('\\n')[0] || '').trim();
    return t;
});
"""

SCRIPT_INSTAGRAM_DIALOG = """
const root = document.querySelector('[role="dialog"]')
    || document.querySelector('[aria-modal="true"]') || document;
return [...root.querySelectorAll('a[href^="/"]')].map(a => {
    const href = (a.getAttribute('href') || '').replace(/^\\//,'').replace(/\\/$/,'');
    if (!href || href.includes('/') || ['p','reel','reels','explore','stories','accounts'].includes(href.toLowerCase())) return '';
    const t = ((a.innerText || '').split('\\n').map(x => x.trim()).filter(Boolean)[0] || '').trim();
    return t || href;
});
"""

SCRIPT_FACEBOOK_LISTA = """
const root = document.querySelector('[role="dialog"]') || document.querySelector('[role="main"]') || document.body;
return [...root.querySelectorAll('[role="listitem"] a, [role="article"] a, a[href*="/pages/"], a[role="link"]')].map(a => {
    return ((a.innerText || '').split('\\n')[0] || '').trim();
});
"""

SCRIPT_CLICK_IG = """
const tipo = arguments[0];
const raiz = document.querySelector('header') || document;
const nodos = [...raiz.querySelectorAll('a, [role="link"], button, li')];
for (const a of nodos) {
    const href = (a.getAttribute('href') || '').toLowerCase();
    const t = (a.innerText || '').toLowerCase().replace(/\\s+/g, ' ').trim();
    const esSeguidos = href.includes('/following')
        || /\\d[\\d.\\s]*\\s*(seguidos|following)\\b/.test(t)
        || t === 'seguidos' || t === 'following';
    const esSeguidores = (href.includes('/followers') && !href.includes('/following'))
        || /\\d[\\d.\\s]*\\s*(seguidores|followers)\\b/.test(t);
    if (tipo === 'following' && esSeguidos) { a.click(); return true; }
    if (tipo === 'followers' && esSeguidores && !esSeguidos) { a.click(); return true; }
}
return false;
"""

SCRIPT_CLICK_LINKEDIN_SEGUIDORES = """
for (const a of document.querySelectorAll('a')) {
    const t = (a.innerText || '').toLowerCase();
    const href = (a.getAttribute('href') || '').toLowerCase();
    if (t.includes('seguidor') || t.includes('follower') || href.includes('/followers')
        || href.includes('overlay/followers')) {
        a.click();
        return true;
    }
}
return false;
"""

SCRIPT_CERRAR_DIALOGO = """
const d = document.querySelector('[role="dialog"]');
if (!d) return false;
const btn = d.querySelector('[aria-label="Cerrar"], [aria-label="Close"], [aria-label="close"]');
if (btn) { btn.click(); return true; }
return false;
"""


def _esperar(driver, js, segundos=12):
    t0 = time.time()
    while time.time() - t0 < segundos:
        try:
            if driver.execute_script(js):
                return True
        except Exception:
            pass
        time.sleep(0.35)
    return False


def recolectar_lista(driver, script, tope=TOPE_LISTA, estancadas=6, espera=0.65, max_segundos=80):
    """Lee nombres y hace scroll del listado hasta que no entren más."""
    vistos, claves = [], set()
    iguales = 0
    t0 = time.time()
    while len(vistos) < tope and iguales < estancadas and (time.time() - t0) < max_segundos:
        try:
            lote = driver.execute_script(script) or []
        except Exception:
            lote = []
        nuevos = 0
        for crudo in lote:
            nombre = limpiar_nombre(crudo)
            clave = _n(nombre)
            if not nombre or clave in claves:
                continue
            claves.add(clave)
            vistos.append(nombre)
            nuevos += 1
            if len(vistos) >= tope:
                break
        if nuevos == 0:
            iguales += 1
        else:
            iguales = 0
        try:
            driver.execute_script(SCRIPT_SCROLL_LISTA)
        except Exception:
            break
        time.sleep(espera)
    print(f"    {len(vistos)} nombres leídos")
    return vistos[:tope]


def _dueno_de(info):
    return " ".join(p for p in (info.get("nombre"), info.get("handle")) if p)


def _es_conteo(texto):
    t = str(texto or "").strip().lower()
    return bool(re.fullmatch(r"[\d.,\s]+(?:mil|mill\.?|k|m)?", t))


def lista_nombres(valor):
    """Nombres reales. Un recuento tipo «186» o «1.543» no es una lista."""
    if isinstance(valor, (list, tuple)):
        crudos = [x for x in valor if not isinstance(x, (int, float))]
    elif isinstance(valor, str):
        if _es_conteo(valor):
            return []
        crudos = [p.strip() for p in re.split(r",\s*", valor.split(":", 1)[-1]) if p.strip()]
    else:
        return []
    return limpiar_nombres(crudos)


def _fusionar(info, clave, nuevos):
    previos = lista_nombres(info.get(clave))
    info[clave] = limpiar_nombres(previos + list(nuevos or []),
                                  excluir=(_dueno_de(info),), tope=TOPE_LISTA)
    return info


def aplicar_a_info(info, seguidas=None, seguidores=None, sigue_a=None,
                   intereses=None, posts=None):
    """Rellena seguidores, a quién sigue y páginas de las que hace repost."""
    info = dict(info or {})
    dueno = _dueno_de(info)
    if seguidores is not None:
        _fusionar(info, "seguidores", seguidores)
    if sigue_a is not None:
        _fusionar(info, "sigue_a", sigue_a)
    if intereses is not None:
        _fusionar(info, "sigue_a", intereses)
    if seguidas is not None:
        _fusionar(info, "sigue_a", seguidas)
    ranking = rankear_reposts(posts, dueno=dueno) if posts is not None else (
        info.get("reposts") or [])
    if posts is not None:
        info["reposts"] = ranking
    n_seg = len(lista_nombres(info.get("seguidores")))
    n_sigue = len(lista_nombres(info.get("sigue_a")))
    n_rp = len(info.get("reposts") or [])
    partes = []
    if n_seg:
        partes.append(f"{n_seg} seguidores")
    if n_sigue:
        partes.append(f"{n_sigue} cuentas o páginas que sigue")
    if n_rp:
        partes.append(f"{n_rp} con repost")
    info["resumen_red"] = (", ".join(partes) + ".") if partes else ""
    if info.get("sigue_a"):
        info["paginas_seguidas"] = formatear_seguidas(info["sigue_a"])
    return info


def hechos_de_red(info):
    """Un hecho por persona/página, para la pestaña de seguidores e intereses."""
    info = info or {}
    hechos = []
    dueno = info.get("nombre") or "esta persona"

    def agregar(categoria, nombre, detalle):
        nombre = limpiar_nombre(nombre)
        if not nombre:
            return
        hechos.append({
            "categoria": categoria,
            "titulo": nombre[:120],
            "contenido": detalle[:400],
        })

    for nombre in lista_nombres(info.get("seguidores")):
        agregar("Seguidor", nombre, f"Sigue a {dueno} en esta red.")
    for nombre in lista_nombres(info.get("sigue_a")):
        agregar("Sigue a", nombre, f"{dueno} sigue esta cuenta, página o grupo.")
    for nombre, n in info.get("reposts") or []:
        veces = "un repost" if n == 1 else f"{n} reposts"
        agregar("Repost", nombre, f"{dueno} compartió o reposteó contenido de esta cuenta ({veces}).")
    return hechos


def _ir(driver, url, espera=2.5):
    try:
        driver.get(url)
        time.sleep(espera)
        return True
    except Exception:
        return False


def _click_js(driver, script, *args):
    try:
        return bool(driver.execute_script(script, *args))
    except Exception:
        return False


def _cerrar_dialogo(driver):
    if _click_js(driver, SCRIPT_CERRAR_DIALOGO):
        time.sleep(0.6)
        return
    try:
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        time.sleep(0.5)
    except Exception:
        pass


def extraer_red_social(driver, red, profile_url, info, posts=None):
    """Abre seguidores, following e intereses de la red y los deja en info."""
    info = dict(info or {})
    info.setdefault("perfil", profile_url)
    info["_red_intentada"] = True
    red = (red or "").lower()
    base = (profile_url or "").rstrip("/")
    print(f"  Leyendo seguidores e intereses en {red}…")

    if isinstance(info.get("seguidores"), str):
        info["n_seguidores"] = info.get("n_seguidores") or info["seguidores"]
        info["seguidores"] = []

    hay_dialogo = (
        "const d = document.querySelector('[role=\"dialog\"], [aria-modal=\"true\"]');"
        "if (!d) return false;"
        "if (d.querySelector('[aria-label=\"Cargando\"], [aria-label=\"Loading\"]')) return false;"
        "return d.querySelectorAll('a[href^=\"/\"]').length > 0;"
    )

    if red == "x":
        if _ir(driver, base + "/following"):
            _fusionar(info, "sigue_a", recolectar_lista(driver, SCRIPT_X_CELDAS))
        if _ir(driver, base + "/followers"):
            _fusionar(info, "seguidores", recolectar_lista(driver, SCRIPT_X_CELDAS, tope=80, max_segundos=35))
    elif red == "instagram":
        handle = info.get("handle") or handle_de_url(profile_url, "instagram")
        _ir(driver, base + "/")
        abierto = _click_js(driver, SCRIPT_CLICK_IG, "following")
        if not abierto or not _esperar(driver, hay_dialogo, 8):
            if handle:
                _ir(driver, f"https://www.instagram.com/{handle}/following/")
        if _esperar(driver, hay_dialogo, 16):
            time.sleep(1.0)
            _fusionar(info, "sigue_a", recolectar_lista(driver, SCRIPT_INSTAGRAM_DIALOG, tope=250))
        _cerrar_dialogo(driver)
        abierto_f = _click_js(driver, SCRIPT_CLICK_IG, "followers")
        if not abierto_f or not _esperar(driver, hay_dialogo, 6):
            if handle:
                _ir(driver, f"https://www.instagram.com/{handle}/followers/")
        if _esperar(driver, hay_dialogo, 8):
            _fusionar(info, "seguidores", recolectar_lista(
                driver, SCRIPT_INSTAGRAM_DIALOG, tope=60, max_segundos=25))
        _cerrar_dialogo(driver)
    elif red == "facebook":
        urls = _urls_facebook_red(profile_url)
        if _ir(driver, urls["following"]):
            _fusionar(info, "sigue_a", recolectar_lista(driver, SCRIPT_FACEBOOK_LISTA))
        if _ir(driver, urls["likes"]):
            _fusionar(info, "sigue_a", recolectar_lista(driver, SCRIPT_FACEBOOK_LISTA))
        if _ir(driver, urls["groups"]):
            _fusionar(info, "sigue_a", recolectar_lista(driver, SCRIPT_FACEBOOK_LISTA))
        if _ir(driver, urls["followers"]):
            _fusionar(info, "seguidores", recolectar_lista(
                driver, SCRIPT_FACEBOOK_LISTA, tope=80, max_segundos=35))
    elif red == "linkedin":
        for ruta in ("details/interests/", "details/interests/companies/",
                     "details/interests/groups/", "details/interests/schools/",
                     "details/interests/influencers/", "details/interests/newsletters/"):
            if _ir(driver, base + "/" + ruta):
                _fusionar(info, "sigue_a", recolectar_lista(driver, SCRIPT_LINKEDIN_INTERESES, tope=200))
        if _ir(driver, base + "/"):
            if _click_js(driver, SCRIPT_CLICK_LINKEDIN_SEGUIDORES):
                time.sleep(2.2)
            else:
                _ir(driver, base + "/overlay/followers/")
            _fusionar(info, "seguidores", recolectar_lista(
                driver, SCRIPT_LINKEDIN_PERSONAS, tope=80, max_segundos=35))
            _cerrar_dialogo(driver)

    info = aplicar_a_info(info, posts=posts)
    n = info.get("resumen_red") or "sin listas visibles"
    print(f"  Red social: {n}")
    return info


def _urls_facebook_red(profile_url):
    base = (profile_url or "").rstrip("/")
    if "profile.php" in base.lower():
        sep = "&" if "?" in base else "?"
        return {
            "followers": f"{base}{sep}sk=followers",
            "following": f"{base}{sep}sk=following",
            "likes": f"{base}{sep}sk=likes",
            "groups": f"{base}{sep}sk=groups",
        }
    return {
        "followers": f"{base}/followers",
        "following": f"{base}/following",
        "likes": f"{base}/likes",
        "groups": f"{base}/groups",
    }


def urls_likes_y_seguidos(profile_url):
    u = _urls_facebook_red(profile_url)
    return [u["likes"], u["following"], u["followers"]]
