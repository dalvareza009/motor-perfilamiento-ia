# instagram_activity_scraper.py
"""
Extractor de Instagram con TU propia sesión: ficha, descripciones de las fotos
y publicaciones reposteadas. De ese texto se guarda lo importante
(familia, edad, trabajo, estudios y ciudad).

Mismo criterio que Facebook y LinkedIn:
- Chrome con perfil persistente propio (``chrome_instagram_profile/``) más
  ``instagram_cookies.json`` de respaldo. Si Instagram pide login, el navegador
  queda abierto y se espera tu confirmación (consola o front), no se cierra.
- Solo se analizan publicaciones de los últimos 365 días.
- La relevancia y las recomendaciones salen del mismo motor del proyecto.
- Las fechas de sistema (``2026-09-01 - None``) no se guardan.

Uso:
    python instagram_activity_scraper.py https://www.instagram.com/usuario/
"""
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app import runtime_nube
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from linkedin_activity_scraper import LinkedInActivityScraper, extraer_red_de, parse_fecha_publicacion
from app.redes_seguidas import elegir_publicaciones, tope_publicaciones

MARCAS_MURO_IG = ("/accounts/login", "/challenge", "/accounts/suspended")
_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio",
          "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")
RUIDO_FICHA = {
    "seguir", "siguiendo", "mensaje", "mensajes", "opciones", "publicaciones",
    "seguidores", "seguidos", "followers", "following", "posts", "ver traducción",
    "see translation", "más", "sugerencias", "compartir", "guardar", "me gusta",
    "comentar", "reels", "etiquetados", "tagged", "inicio", "buscar", "explorar",
    "notificaciones", "crear", "perfil", "hilos", "threads", "información",
    "descargar", "abrir en la app", "iniciar sesión", "log in", "sign up",
    "registrarte", "ahora no", "not now", "contactar", "cuentas similares",
    "similar accounts", "esta cuenta es privada", "this account is private",
    "sigue esta cuenta para ver sus fotos y videos",
    "follow this account to see their photos and videos",
}
RUIDO_POST = RUIDO_FICHA | {
    "responder", "ver los comentarios", "view all comments", "liked by",
    "otras personas", "meta", "información", "blog",
}


def es_cuenta_privada(texto):
    t = (texto or "").lower()
    return "esta cuenta es privada" in t or "this account is private" in t


def es_no_disponible(texto):
    t = (texto or "").lower()
    return ("esta página no está disponible" in t or "sorry, this page isn't available" in t
            or "this page isn't available" in t)


def tiempo_legible(etiqueta, datetime_attr=""):
    """Deja «3 sem» o «1 de septiembre de 2026». No guarda el instante ISO."""
    etiqueta = re.sub(r"\s+", " ", (etiqueta or "")).strip()
    es_iso = bool(re.match(r"\d{4}-\d{2}-\d{2}", etiqueta))
    if etiqueta and not es_iso and parse_fecha_publicacion(etiqueta):
        return etiqueta
    fecha = parse_fecha_publicacion(datetime_attr) or (parse_fecha_publicacion(etiqueta) if es_iso else None)
    if fecha:
        return f"{fecha.day} de {_MESES[fecha.month - 1]} de {fecha.year}"
    return "" if es_iso else etiqueta


_ALT_BASURA = re.compile(
    r"^(photo by|foto de|image may contain|puede contener|may be an image|may be a |"
    r"imagen de perfil|foto del perfil|foto de perfil)\b", re.I)
_REPOST = re.compile(r"reposte[oó]|reposteo|reposted|\brepost\b", re.I)
_CORTE_COMENTARIOS = re.compile(
    r"^(ver (todos )?los comentarios|view all( \d+)? comments|agregar un comentario|add a comment)$", re.I)
_LOGRO_IG = re.compile(
    r"\b(feliz de haber|me felicito|orgullos[oa] de|logr[eéoa]\w*|me gradu\w*|mi t[ií]tulo|"
    r"certificad[oa]|premio|reconocimient\w*|nombrad[oa]|ascend[ií])\b", re.I)


def alt_util(texto):
    """Descripción de la foto que escribió la persona. Descarta el texto automático."""
    t = re.sub(r"\s+", " ", (texto or "")).strip()
    if len(t) < 12 or _ALT_BASURA.match(t):
        return ""
    return t


def es_repost(texto):
    return bool(_REPOST.search(texto or ""))


def es_logro(texto):
    """La persona se felicita o sube un logro. No aplica a un comentario de otra cuenta."""
    return bool(_LOGRO_IG.search(texto or ""))


def caption_de_publicacion(titulo, articulo):
    """El texto de la persona: caption o, si no hay, la descripción de la foto. Sin comentarios."""
    from app.perfil_redes import quitar_fechas_iso

    def limpia(linea):
        return quitar_fechas_iso(re.sub(r"\s+", " ", linea or "").strip())

    titulo = limpia(titulo)
    if len(titulo) > 20 and titulo.lower() not in RUIDO_POST and not _CORTE_COMENTARIOS.match(titulo.lower()):
        return titulo
    lineas = []
    for linea in str(articulo or "").splitlines():
        t = limpia(linea)
        bajo = t.lower()
        if not t or _CORTE_COMENTARIOS.match(bajo):
            if _CORTE_COMENTARIOS.match(bajo):
                break
            continue
        if bajo in RUIDO_POST or re.match(r"^[\d.,]+\s*(me gusta|likes|comentarios|comments)", bajo):
            continue
        lineas.append(t)
    return "\n".join(lineas)


def incorporar_datos_importantes(info, posts):
    """Del caption o del repost: familia, edad, trabajo, estudios, ciudad y logros propios.

    Los comentarios no llegan aquí: el texto del post ya viene sin ellos.
    """
    from app import linkedin_texto
    from app.perfil_redes import _n, categorias_oracion, quitar_fechas_iso

    info = dict(info or {})
    logros = [info.get("logros") or ""]
    for post in posts or []:
        texto = post.get("texto") or ""
        if not texto or linkedin_texto.evaluar_publicacion(texto)["omitida"]:
            continue
        for oracion in re.split(r"(?<=[.!?])\s+|\n", texto):
            frase = quitar_fechas_iso(re.sub(r"\s+", " ", oracion).strip(" ."))
            if not frase or (es_repost(frase) and len(frase) < 40):
                continue
            if post.get("tipo") != "compartida" and es_logro(frase) and _n(frase) not in _n(" ".join(logros)):
                logros.append(frase)
            for cat in categorias_oracion(frase):
                campo = {"Familia": "familia", "Edad": "edad", "Trabajo": "experiencia",
                         "Estudios": "educacion", "Ubicacion": "ubicacion"}.get(cat)
                if not campo:
                    continue
                actual = info.get(campo) or ""
                if _n(frase) and _n(frase) not in _n(actual):
                    info[campo] = ". ".join(p for p in (actual, frase) if p)
    info["logros"] = ". ".join(p for p in logros if p)
    if not info.get("titular") and info.get("experiencia"):
        info["titular"] = info["experiencia"].split(". ")[0][:300]
    from app.perfil_redes import aplicar_lo_publicado
    propios = [p for p in (posts or [])
               if not linkedin_texto.evaluar_publicacion(p.get("texto") or "")["omitida"]]
    info = aplicar_lo_publicado(info, propios)
    return info


def url_de_publicacion(href):
    hallado = re.search(r"instagram\.com/(?:[^/]+/)?(p|reel)/([^/?#]+)", href or "", re.I)
    if not hallado:
        return ""
    return f"https://www.instagram.com/{hallado.group(1).lower()}/{hallado.group(2)}/"


def parsear_ficha_instagram(cuerpo, nombre_conocido=""):
    """Saca nombre, bio, ubicación, trabajo, estudios y familia del texto del perfil.

    Instagram mezcla la ficha con botones; aquí se deja solo lo que describe a la persona.
    """
    from app.perfil_redes import aplicar_lo_publicado, quitar_fechas_iso

    info = {"nombre": (nombre_conocido or "").strip(), "titular": "", "ubicacion": "",
            "acerca": "", "experiencia": "", "educacion": "", "estado_civil": "",
            "seguidores": "", "privado": False, "no_disponible": False}
    texto = str(cuerpo or "")
    info["privado"] = es_cuenta_privada(texto)
    info["no_disponible"] = es_no_disponible(texto)
    hallados = re.search(
        r"([\d.,]+\s*(?:mil|mill\.?)?)\s*(?:seguidores|followers)\b", texto, re.I)
    if hallados:
        info["seguidores"] = re.sub(r"\s+", " ", hallados.group(1)).strip()

    trabajo, estudios, civil, resto = [], [], [], []
    for linea in texto.splitlines():
        t = quitar_fechas_iso(re.sub(r"\s+", " ", linea).strip())
        bajo = t.lower().strip(" .•·")
        if not t or bajo in RUIDO_FICHA or re.fullmatch(r"[\d.,]+\s*(?:mil|mill\.?)?", bajo):
            continue
        if t.lower().startswith("http") or "instagram.com" in bajo:
            continue
        if re.search(r"\bcasad[oa]\b|\bespos[oa]\b|\bmam[áa]\b|\bpap[áa]\b|\bhij[oa]s?\b", bajo):
            civil.append(t)
        elif re.search(r"\b(aut[oó]nom[oa]|independiente|trabaja en|empleado|docente|profesor)\b", bajo):
            trabajo.append(t)
            if re.search(r"\b(universidad|colegio|liceo)\b", bajo):
                estudios.append(t)
        elif re.search(r"\b(universidad|liceo|colegio|pregrado|posgrado)\b", bajo):
            estudios.append(t)
        elif re.match(r"^vive en\b", bajo) or (re.match(r"^de\b", bajo) and len(t) < 80):
            if t not in info["ubicacion"]:
                info["ubicacion"] = ". ".join(p for p in (info["ubicacion"], t) if p)
        elif not info["nombre"] and re.match(r"^[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ.'-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ.'-]+){0,4}$", t) and len(t) < 80:
            info["nombre"] = t[:120]
        elif len(t) > 2:
            resto.append(t)

    if trabajo:
        info["experiencia"] = "Trabajo declarado en el perfil: " + ". ".join(trabajo)
        info["titular"] = trabajo[0]
    if estudios:
        info["educacion"] = "Estudios declarados en el perfil: " + ". ".join(estudios)
    if civil:
        info["estado_civil"] = "Estado civil declarado en el perfil: " + ". ".join(civil)
    if not info["titular"] and resto:
        info["titular"] = resto[0][:300]
    utiles = [p for p in resto if p not in (info["titular"],)][:8]
    if utiles:
        info["bio"] = "\n".join(utiles)[:400]
    elif info.get("titular") and not trabajo:
        info["bio"] = info["titular"]
    info["acerca"] = "\n".join(filter(None, [
        info["titular"], info["ubicacion"], info["experiencia"],
        info["educacion"], info["estado_civil"], *utiles]))
    for clave, valor in list(info.items()):
        if isinstance(valor, str) and valor:
            info[clave] = quitar_fechas_iso(valor)
    return aplicar_lo_publicado(info, [{"tipo": "publicacion", "texto": info.get("acerca") or ""}])


class InstagramActivityScraper:
    def __init__(self, cookie_file='instagram_cookies.json',
                 profile_dir='chrome_instagram_profile', confirmar_login=None):
        self.cookie_file = Path(cookie_file)
        self.profile_dir = Path(profile_dir).resolve()
        self.confirmar_login = confirmar_login
        self.driver = None
        self.info = {}
        self.analisis = LinkedInActivityScraper(
            cookie_file='linkedin_cookies.json', profile_dir='chrome_instagram_profile')
        self.analisis.prefijo_archivos = "instagram"
        # En Instagram la publicación es de la persona: pesa lo mismo que una propia.
        self.analisis.peso_compartida = self.analisis.peso_propia
        self.analisis.priorizar_propias = False

    def _sanitizar(self, raw):
        if not isinstance(raw, dict) or not raw.get("name") or "value" not in raw:
            return None
        domain = str(raw.get("domain") or ".instagram.com")
        if "instagram.com" not in domain:
            return None
        cookie = {"name": str(raw["name"]), "value": str(raw["value"]),
                  "domain": domain, "path": str(raw.get("path") or "/"),
                  "secure": bool(raw.get("secure", True)),
                  "httpOnly": bool(raw.get("httpOnly", False))}
        exp = raw.get("expiry", raw.get("expirationDate"))
        if isinstance(exp, (int, float)) and exp > 0:
            cookie["expiry"] = int(exp)
        if raw.get("sameSite") in ("Strict", "Lax", "None"):
            cookie["sameSite"] = raw["sameSite"]
        return cookie

    def _en_muro_de_login(self):
        url = (self.driver.current_url or "").lower()
        return any(m in url for m in MARCAS_MURO_IG)

    def sesion_activa(self):
        if self.driver is None or self._en_muro_de_login():
            return False
        try:
            nombres = {c["name"] for c in self.driver.get_cookies()}
        except Exception:
            return False
        return "sessionid" in nombres

    def guardar_cookies(self):
        if self.driver is None:
            return
        try:
            cookies = [c for c in self.driver.get_cookies()
                       if "instagram.com" in (c.get("domain") or "")]
            if "sessionid" not in {c["name"] for c in cookies} and self.cookie_file.is_file():
                try:
                    previas = json.loads(self.cookie_file.read_text(encoding="utf-8"))
                    if isinstance(previas, dict):
                        previas = previas.get("cookies", [])
                    if any(c.get("name") == "sessionid" for c in previas if isinstance(c, dict)):
                        print("Sin sesion activa: conservo las cookies anteriores.")
                        return
                except Exception:
                    pass
            self.cookie_file.write_text(json.dumps(cookies, indent=2, ensure_ascii=False),
                                        encoding="utf-8")
            print(f"Cookies de Instagram guardadas ({len(cookies)})")
        except Exception as e:
            print(f"No se pudieron guardar las cookies: {e}")

    def _cerrar_avisos(self):
        try:
            self.driver.execute_script("""
                const textos = ['ahora no', 'not now', 'permitir todas las cookies',
                                'allow all cookies', 'aceptar', 'aceptar todo'];
                for (const b of document.querySelectorAll('button, [role="button"]')) {
                    const t = (b.innerText || '').trim().toLowerCase();
                    if (textos.includes(t)) b.click();
                }
            """)
        except Exception:
            pass

    def esperar_login_manual(self, contexto=""):
        print("\nInstagram esta pidiendo iniciar sesion. El navegador queda abierto:")
        print("   entra con tu cuenta en esa ventana de Chrome y confirma "
              + ("en la pagina web." if self.confirmar_login else "aqui con Enter."))
        if not runtime_nube.login_manual_permitido():
            print("En el servidor no hay login manual: hace falta una cookie de sesion vigente.")
            return False
        while True:
            if self.confirmar_login is not None:
                if self.confirmar_login(contexto) != "continuar":
                    return False
            else:
                try:
                    if input("Enter cuando ya hayas entrado (o 'salir'): ").strip().lower() in ("salir", "q"):
                        return False
                except EOFError:
                    return False
            self.driver.get("https://www.instagram.com/")
            time.sleep(4)
            self._cerrar_avisos()
            if self.sesion_activa():
                self.guardar_cookies()
                return True
            print("Aun no se ve la sesion; termina de entrar y vuelve a confirmar.")

    def iniciar_navegador(self):
        options = Options()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={self.profile_dir}")
        options.add_argument("--window-size=1280,900")
        options.add_argument("--lang=es-ES")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-blink-features=AutomationControlled")
        try:
            self.driver = runtime_nube.crear_driver(options)
        except Exception as e:
            print(f"Chrome no arranco: {e} (¿otro Chrome usa ese perfil?)")
            return False
        self.driver.get("https://www.instagram.com/")
        time.sleep(4)
        self._cerrar_avisos()
        if self.sesion_activa():
            print("Sesion de Instagram activa (perfil de Chrome)")
            self.guardar_cookies()
            return True
        if self.cookie_file.is_file():
            try:
                datos = json.loads(self.cookie_file.read_text(encoding="utf-8"))
                if isinstance(datos, dict) and isinstance(datos.get("cookies"), list):
                    datos = datos["cookies"]
                for raw in datos if isinstance(datos, list) else []:
                    cookie = self._sanitizar(raw)
                    if cookie:
                        try:
                            self.driver.add_cookie(cookie)
                        except Exception:
                            continue
                self.driver.get("https://www.instagram.com/")
                time.sleep(4)
                self._cerrar_avisos()
                if self.sesion_activa():
                    print("Sesion de Instagram activa (cookies)")
                    self.guardar_cookies()
                    return True
            except Exception as e:
                print(f"Cookies de Instagram no utilizables: {e}")
        return self.esperar_login_manual("inicio del bot de Instagram")

    def cerrar_navegador(self, preguntar=True):
        if self.driver is None:
            return
        self.guardar_cookies()
        if preguntar:
            try:
                input("\nPulsa Enter para cerrar el navegador... ")
            except EOFError:
                pass
        try:
            self.driver.quit()
        except Exception:
            pass
        self.driver = None

    def _texto_header(self):
        try:
            return self.driver.execute_script(
                "const h = document.querySelector('header'); return h ? h.innerText : '';") or ""
        except Exception:
            return ""

    def _nombre_visible(self):
        try:
            titulo = self.driver.execute_script(
                "const m = document.querySelector('meta[property=\"og:title\"]');"
                "return m ? (m.content || '') : '';") or ""
        except Exception:
            titulo = ""
        hallado = re.match(r"(.+?)\s*\(@", titulo)
        if hallado:
            return hallado.group(1).strip()[:120]
        try:
            texto = self.driver.find_element(By.CSS_SELECTOR, "header h1, header h2").text.strip()
            if texto and texto.lower() not in RUIDO_FICHA:
                return texto.splitlines()[0][:120]
        except Exception:
            pass
        return ""

    def _leer_bio(self):
        """El texto que la persona escribió bajo el nombre, no los recuentos."""
        try:
            return (self.driver.execute_script("""
                const header = document.querySelector('header');
                if (!header) return '';
                const ul = header.querySelector('ul');
                const nombre = ((header.querySelector('h1, h2') || {}).innerText || '').trim();
                let mejor = '';
                for (const n of header.querySelectorAll('span, div')) {
                    if (ul && ul.contains(n)) continue;
                    const t = (n.innerText || '').trim();
                    if (!t || t === nombre || t.length < 3 || t.length > 500) continue;
                    if (/^(seguidores|seguidos|publicaciones|followers|following|posts)$/i.test(t)) continue;
                    if (/^[\\d.,\\s]+$/.test(t)) continue;
                    if (t.length >= mejor.length) mejor = t;
                }
                return mejor;
            """) or "").strip()
        except Exception:
            return ""

    def extraer_informacion_perfil(self, profile_url):
        print(f"\nLeyendo primero la ficha de Instagram: {profile_url}")
        self.driver.get(profile_url)
        time.sleep(4)
        self._cerrar_avisos()
        if self._en_muro_de_login():
            if not self.esperar_login_manual(profile_url):
                return {}
            self.driver.get(profile_url)
            time.sleep(4)
        try:
            cuerpo = self.driver.find_element(By.TAG_NAME, "body").text or ""
        except Exception:
            cuerpo = ""
        header = self._texto_header() or cuerpo
        info = parsear_ficha_instagram(header + "\n" + cuerpo[:2500], self._nombre_visible())
        bio = self._leer_bio()
        if bio:
            info["bio"] = bio[:400]
            if not info.get("titular"):
                info["titular"] = bio.splitlines()[0][:300]
        info["perfil"] = profile_url
        from app.redes_seguidas import handle_de_url
        info["handle"] = handle_de_url(profile_url, "instagram")
        if info["no_disponible"]:
            print("  Instagram no muestra este perfil.")
        elif info["privado"]:
            print(f"  Cuenta privada: {info['nombre'] or 'sin nombre'}. Se guarda la ficha visible.")
        else:
            print(f"  OK {info['nombre'] or 'Perfil de Instagram'}"
                  + (f" · {info['seguidores']} seguidores" if info.get("seguidores") else ""))
        if not info.get("privado") and not info.get("no_disponible"):
            info = extraer_red_de(self.driver, "instagram", profile_url, info)
        self.info = info
        self.analisis.info_perfil[profile_url] = info
        return info

    def _recoger_enlaces(self, tope):
        vistos, reposts = [], set()
        for _ronda in range(6):
            try:
                hrefs = self.driver.execute_script("""
                    return [...document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]')].map(a => {
                        const label = [...a.querySelectorAll('[aria-label]')]
                            .map(n => n.getAttribute('aria-label') || '').join(' ');
                        return {href: a.href, repost: /repost/i.test(label)};
                    });
                """) or []
            except Exception:
                hrefs = []
            for item in hrefs:
                href = item.get("href") if isinstance(item, dict) else item
                limpia = url_de_publicacion(href)
                if not limpia or limpia in vistos:
                    continue
                vistos.append(limpia)
                if isinstance(item, dict) and item.get("repost"):
                    reposts.add(limpia)
            if len(vistos) >= tope:
                break
            self.driver.execute_script("window.scrollBy(0, 1100);")
            time.sleep(2)
        return vistos[:tope], reposts

    def _leer_publicacion(self, profile_url, url_post, es_repost_grid=False):
        self.driver.get(url_post)
        time.sleep(3)
        self._cerrar_avisos()
        try:
            self.driver.execute_script("""
                for (const b of document.querySelectorAll('button, [role="button"]')) {
                    const t = (b.innerText || '').trim().toLowerCase();
                    if (t === 'más' || t === 'more' || t === '... más' || t === 'ver más') b.click();
                }
            """)
        except Exception:
            pass
        try:
            propio = (self.info.get("handle") or "").lower()
            datos = self.driver.execute_script("""
                const propio = (arguments[0] || '').toLowerCase();
                const time = document.querySelector('time');
                const h1 = document.querySelector('h1');
                const article = document.querySelector('article') || document.body;
                const sinComentarios = article.cloneNode(true);
                sinComentarios.querySelectorAll('ul').forEach(n => n.remove());
                const alts = [...article.querySelectorAll('img')].map(img => img.alt || '').filter(Boolean);
                const etiquetas = [...article.querySelectorAll('[aria-label]')]
                    .map(n => n.getAttribute('aria-label') || '').join(' ');
                const handles = [...article.querySelectorAll('a[href^="/"]')].map(a =>
                    (a.getAttribute('href') || '').replace(/^\\//,'').replace(/\\/$/,'')
                ).filter(h => h && !h.includes('/') && !['p','reel','reels','explore','stories'].includes(h.toLowerCase()));
                const origen = handles.find(h => h.toLowerCase() !== propio) || '';
                return {
                    datetime: time ? (time.getAttribute('datetime') || '') : '',
                    etiqueta: time ? (time.innerText || '') : '',
                    titulo: h1 ? (h1.innerText || '') : '',
                    articulo: sinComentarios.innerText || '',
                    alts: alts,
                    origen: origen,
                    repost: /reposte[oó]|reposted|\\brepost\\b/i.test((article.innerText || '') + ' ' + etiquetas)
                };
            """, propio) or {}
        except Exception:
            return None
        base = caption_de_publicacion(datos.get("titulo") or "", datos.get("articulo") or "")
        if len(base) < 25:
            descripciones = [alt_util(a) for a in (datos.get("alts") or [])]
            base = "\n".join(filter(None, [base, *descripciones]))
        texto = self.analisis._limpiar_texto(base, limite=2000)
        if len(texto) < 25:
            return None
        tiempo = tiempo_legible(datos.get("etiqueta") or "", datos.get("datetime") or "")
        repost = es_repost_grid or bool(datos.get("repost")) or es_repost(texto[:240])
        autor = (datos.get("origen") or "").strip() if repost else (self.info.get("nombre") or "")
        if not autor:
            autor = self.info.get("nombre") or ""
        return {
            "perfil": profile_url, "urn": "N/A", "url_publicacion": url_post,
            "tipo": "compartida" if repost else "publicacion",
            "autor": autor,
            "texto": texto, "tiempo": tiempo,
            "hashtags": ";".join(self.analisis.extraer_hashtags(texto)),
            "enlaces": "", "reacciones": "", "comentarios": "",
            "fecha_extraccion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _elegir(self, publicaciones, max_posts):
        """Hasta max_posts en total. Los reposts que encajan con el catálogo entran primero."""
        from app.linkedin_texto import evaluar_publicacion

        def de_catalogo(post):
            if post.get("tipo") != "compartida":
                return False
            ev = evaluar_publicacion(post.get("texto") or "")
            return not ev["omitida"] and bool(ev["intereses"])

        def grupo_de(post):
            return "compartida" if post.get("tipo") == "compartida" else "propia"

        return elegir_publicaciones(publicaciones, max_posts, grupo_de, de_catalogo)

    def extraer_publicaciones(self, profile_url, max_posts=10):
        max_posts = tope_publicaciones(max_posts)
        if self.info.get("privado") or self.info.get("no_disponible"):
            print("  Sin publicaciones: la cuenta es privada o no esta disponible.")
            return []
        print(f"\nLeyendo descripciones y reposts de {profile_url}")
        self.driver.get(profile_url if profile_url.endswith("/") else profile_url + "/")
        time.sleep(4)
        enlaces, reposts = self._recoger_enlaces(max_posts * 3)
        handle = self.info.get("handle") or ""
        if handle:
            self.driver.get(f"https://www.instagram.com/{handle}/reposts/")
            time.sleep(3)
            self._cerrar_avisos()
            if "/reposts" in (self.driver.current_url or "").lower():
                mas, _ = self._recoger_enlaces(max_posts * 2)
                for url_post in mas:
                    if url_post not in enlaces:
                        enlaces.append(url_post)
                    reposts.add(url_post)
                print(f"  {len(mas)} en el apartado de reposts")
        publicaciones, recientes, antiguas_seguidas = [], 0, 0
        hoy = datetime.now().date()
        for url_post in enlaces:
            post = self._leer_publicacion(profile_url, url_post, url_post in reposts)
            if not post:
                continue
            fecha = parse_fecha_publicacion(post.get("tiempo") or "")
            publicaciones.append(post)
            if fecha and (hoy - fecha).days > 365:
                antiguas_seguidas += 1
                if antiguas_seguidas >= 2:
                    break
                continue
            antiguas_seguidas = 0
            recientes += 1
            print(f"  [{recientes}] {post['texto'][:60]}...")
        vigentes = self._elegir(self.analisis.filtrar_y_ordenar(publicaciones), max_posts)
        self.info = incorporar_datos_importantes(self.info, vigentes)
        from app.redes_seguidas import aplicar_a_info
        self.info = aplicar_a_info(self.info, posts=vigentes)
        self.analisis.info_perfil[profile_url] = self.info
        print(f"  OK {len(vigentes)} dentro del ultimo año "
              f"({self.analisis.ultimas_descartadas} antiguas descartadas, "
              f"{sum(1 for p in vigentes if p.get('tipo') == 'compartida')} reposts)")
        return vigentes[:max_posts]

    def ejecutar(self, profile_url, max_posts=10):
        if not self.iniciar_navegador():
            self.cerrar_navegador(preguntar=False)
            return {"ok": False, "motivo": "No se confirmo el inicio de sesion en Instagram."}
        try:
            info = self.extraer_informacion_perfil(profile_url)
            posts = self.extraer_publicaciones(profile_url, max_posts=max_posts)
            info = self.info or info
            self.analisis.analizar_publicaciones(posts)
            self.analisis.imprimir_recomendaciones()
            archivos = self.analisis.guardar_resultados()
            return {"ok": True, "perfil": profile_url, "perfil_info": info,
                    "publicaciones": len(posts),
                    "descartadas_antiguas": self.analisis.descartadas_antiguas,
                    "omitidas_sensibles": sum(self.analisis.omitidas_sensibles.values()),
                    "recomendaciones": self.analisis.recomendaciones,
                    "archivos": archivos}
        finally:
            self.cerrar_navegador(preguntar=False)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Instagram: ficha + publicaciones del ultimo año -> recomendaciones")
    parser.add_argument("url", help="https://www.instagram.com/usuario/")
    parser.add_argument("--max-posts", type=int, default=10)
    args = parser.parse_args()
    bot = InstagramActivityScraper()
    try:
        resultado = bot.ejecutar(args.url, max_posts=args.max_posts)
        print(resultado.get("motivo", "Listo."))
    except Exception as e:
        bot.cerrar_navegador(preguntar=False)
        raise SystemExit(f"Error: {e}") from None
