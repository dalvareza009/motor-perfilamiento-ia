# x_activity_scraper.py
"""
Extractor de X (Twitter) con TU propia sesión: ficha, publicaciones,
respuestas, republicaciones y logros que la persona dejó por escrito.

Mismo criterio que LinkedIn e Instagram:
- Chrome con perfil persistente (``chrome_x_profile/``) más ``x_cookies.json``.
  Si X pide login, el navegador queda abierto y se espera tu confirmación.
- Solo se analizan publicaciones del último año.
- La relevancia y las recomendaciones salen del mismo motor del proyecto.
- Las fechas de sistema no se guardan. Se conserva «2022 - actualidad».

Uso:
    python x_activity_scraper.py https://x.com/usuario
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

from instagram_activity_scraper import tiempo_legible
from linkedin_activity_scraper import LinkedInActivityScraper, parse_fecha_publicacion

MARCAS_MURO_X = ("/i/flow/login", "/login", "/i/flow/signup", "/account/access")
RUIDO_FICHA = {
    "seguir", "siguiendo", "follow", "following", "mensaje", "mensajes",
    "publicaciones", "posts", "respuestas", "replies", "destacados", "highlights",
    "artículos", "articulos", "articles", "fotos y videos", "media", "me gusta",
    "likes", "seguidores", "followers", "suscribirse", "subscribe", "editar perfil",
    "edit profile", "más", "more", "mostrar más", "show more", "ver más",
    "inicio", "explorar", "explore", "notificaciones", "mensajes", "buscar",
    "premium", "verificar", "verified", "compartir perfil", "share profile",
}
_LOGRO = re.compile(
    r"\b(gradu[eéó]|titulad[oa]|certificad[oa]|premio|reconocimient|logr[eé]|ascend[ií]|nombrad[oa]|"
    r"medalla|campe[oó]n|publiqu[eé]|fund[eé]|emprend[ií]|aniversario|promoci[oó]n|beca|"
    r"doctorado|maestr[ií]a|habilitad[oa]|obtuve|complet[eé])\b", re.I)
_REPOST = re.compile(r"\b(repost|reposte[oó]|republic[oó]|retweeted|reposted)\b", re.I)
_RESPUESTA = re.compile(r"en respuesta a|replying to", re.I)
_PROTEGIDA = re.compile(r"publicaciones est[aá]n protegidas|posts are protected|these posts are protected", re.I)
_AUSENTE = re.compile(r"esta cuenta no existe|this account doesn.?t exist|account suspended|cuenta suspendida", re.I)


def url_pide_login(url):
    u = (url or "").lower()
    return any(m in u for m in MARCAS_MURO_X)


def es_cuenta_protegida(texto):
    return bool(_PROTEGIDA.search(texto or ""))


def es_no_disponible(texto):
    return bool(_AUSENTE.search(texto or ""))


def es_repost(texto):
    return bool(_REPOST.search(texto or ""))


def es_respuesta(texto):
    return bool(_RESPUESTA.search(texto or ""))


def es_logro(texto):
    return bool(_LOGRO.search(texto or ""))


def url_de_publicacion(href):
    hallado = re.search(r"(?:x|twitter)\.com/([^/?#]+)/status/(\d+)", href or "", re.I)
    if not hallado:
        return ""
    usuario = hallado.group(1)
    if usuario.lower() in {"i", "home", "search", "explore", "intent"}:
        return ""
    return f"https://x.com/{usuario}/status/{hallado.group(2)}"


def _numero(texto):
    """Primer conteo de un aria-label («12 respuestas», «1.234 Me gusta», «12,3 mil»)."""
    bruto = re.search(r"(\d[\d.,]*)", texto or "")
    if not bruto:
        return 0
    token = bruto.group(1)
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", token):
        n = int(token.replace(".", ""))
    elif re.fullmatch(r"\d{1,3}(,\d{3})+", token):
        n = int(token.replace(",", ""))
    elif re.fullmatch(r"\d+[.,]\d+", token):
        n = float(token.replace(",", "."))
    else:
        n = int(re.sub(r"\D", "", token) or 0)
    if re.search(r"\b(mil|k)\b", (texto or "").lower()):
        n = int(n * 1000)
    return int(n)


def resumir_interacciones(posts):
    """Conteo de lo leído: respuestas, republicaciones y reacciones visibles."""
    posts = posts or []
    respuestas = sum(1 for p in posts if p.get("tipo") == "respuesta")
    reposts = sum(1 for p in posts if p.get("tipo") == "compartida")
    propias = [p for p in posts if p.get("tipo") != "compartida"]

    def suma(campo):
        return sum(_numero(p.get(campo)) for p in propias)

    partes = []
    if respuestas:
        partes.append(f"{respuestas} respuestas propias leídas")
    if reposts:
        partes.append(f"{reposts} republicaciones leídas")
    recibidas = suma("respuestas_n")
    amplificadas = suma("reposts_n")
    gustos = suma("me_gusta")
    if recibidas or amplificadas or gustos:
        partes.append(
            f"en las publicaciones propias: {recibidas} respuestas, {amplificadas} republicaciones y {gustos} me gusta")
    if not partes:
        return ""
    return "Interacciones en el perfil: " + "; ".join(partes)


def incorporar_datos_importantes(info, posts):
    """De cada publicación, respuesta o logro se queda lo que describe a la persona."""
    from app import linkedin_texto
    from app.perfil_redes import _n, categorias_oracion, quitar_fechas_iso

    info = dict(info or {})
    logros = [info.get("logros") or ""]
    for post in posts or []:
        texto = post.get("texto") or ""
        if not texto or post.get("tipo") == "compartida" or linkedin_texto.evaluar_publicacion(texto)["omitida"]:
            continue
        for oracion in re.split(r"(?<=[.!?])\s+|\n", texto):
            frase = quitar_fechas_iso(re.sub(r"\s+", " ", oracion).strip(" ."))
            if not frase or (es_repost(frase) and len(frase) < 40):
                continue
            if es_logro(frase) and _n(frase) and _n(frase) not in _n(" ".join(logros)):
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


def parsear_ficha_x(datos, nombre_conocido=""):
    """Nombre, bio, ubicación, trabajo, estudios, familia y logros del encabezado."""
    from app.perfil_redes import aplicar_lo_publicado, quitar_fechas_iso

    datos = datos or {}
    if isinstance(datos, str):
        datos = {"cuerpo": datos}
    info = {
        "nombre": (nombre_conocido or "").strip(), "titular": "", "ubicacion": "",
        "acerca": "", "experiencia": "", "educacion": "", "estado_civil": "",
        "familia": "", "edad": "", "logros": "", "seguidores": "",
        "privado": False, "no_disponible": False, "en_x_desde": "",
    }
    cuerpo = str(datos.get("cuerpo") or "")
    info["privado"] = bool(datos.get("protegida")) or es_cuenta_protegida(cuerpo)
    info["no_disponible"] = bool(datos.get("ausente")) or es_no_disponible(cuerpo)

    nombre = re.sub(r"\s+", " ", str(datos.get("nombre") or "")).strip()
    if nombre:
        info["nombre"] = nombre.split("@", 1)[0].split("\n", 1)[0].strip()[:120]
    seguidores = re.search(
        r"([\d.,]+\s*(?:mil|mill\.?|k|m)?)\s*(?:seguidores|followers)\b",
        str(datos.get("seguidores") or cuerpo), re.I)
    if seguidores:
        info["seguidores"] = re.sub(r"\s+", " ", seguidores.group(1)).strip()

    unio = quitar_fechas_iso(re.sub(r"\s+", " ", str(datos.get("unio") or "")).strip())
    if unio and not re.search(r"\d{4}-\d{2}-\d{2}", unio):
        info["en_x_desde"] = unio

    profesion = quitar_fechas_iso(re.sub(r"\s+", " ", str(datos.get("profesion") or "")).strip())
    ubicacion = quitar_fechas_iso(re.sub(r"\s+", " ", str(datos.get("ubicacion") or "")).strip())
    if ubicacion and ubicacion.lower() not in RUIDO_FICHA:
        info["ubicacion"] = ubicacion

    trabajo, estudios, civil, logros, resto = [], [], [], [], []
    if profesion and profesion.lower() not in RUIDO_FICHA:
        trabajo.append(profesion)
    lineas = str(datos.get("bio") or "")
    if not lineas.strip():
        lineas = cuerpo
    for linea in lineas.splitlines():
        t = quitar_fechas_iso(re.sub(r"\s+", " ", linea).strip())
        bajo = t.lower().strip(" .•·")
        if not t or bajo in RUIDO_FICHA or t.lower().startswith("http"):
            continue
        if "x.com" in bajo or "twitter.com" in bajo:
            continue
        if re.search(r"\bcasad[oa]\b|\bespos[oa]\b|\bmam[áa]\b|\bpap[áa]\b|\bhij[oa]s?\b|\bherman[oa]\b", bajo):
            civil.append(t)
        elif re.search(r"\b(aut[oó]nom[oa]|independiente|trabaja en|empleado|docente|profesor|ingenier[oa]|analista)\b", bajo):
            trabajo.append(t)
            if re.search(r"\b(universidad|colegio|liceo)\b", bajo):
                estudios.append(t)
        elif re.search(r"\b(universidad|liceo|colegio|pregrado|posgrado|estudi[eé]|estudio)\b", bajo):
            estudios.append(t)
        elif re.match(r"^vive en\b", bajo) or (re.match(r"^de\b", bajo) and len(t) < 80):
            if t not in info["ubicacion"]:
                info["ubicacion"] = ". ".join(p for p in (info["ubicacion"], t) if p)
        elif es_logro(t):
            logros.append(t)
        elif not info["nombre"] and re.match(
                r"^[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ.'-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ.'-]+){0,4}$", t) and len(t) < 80:
            info["nombre"] = t[:120]
        elif len(t) > 2:
            resto.append(t)

    if trabajo:
        info["experiencia"] = "Trabajo declarado en el perfil: " + ". ".join(dict.fromkeys(trabajo))
        info["titular"] = trabajo[0]
    if estudios:
        info["educacion"] = "Estudios declarados en el perfil: " + ". ".join(dict.fromkeys(estudios))
    if civil:
        info["familia"] = "Familia declarada en el perfil: " + ". ".join(dict.fromkeys(civil))
        info["estado_civil"] = info["familia"]
    if logros:
        info["logros"] = ". ".join(dict.fromkeys(logros))
    if not info["titular"] and resto:
        info["titular"] = resto[0][:300]
    utiles = [p for p in resto if p != info["titular"]][:6]
    info["acerca"] = "\n".join(filter(None, [
        info["titular"], info["ubicacion"], info["en_x_desde"], info["experiencia"],
        info["educacion"], info["familia"], info["logros"], *utiles]))
    for clave, valor in list(info.items()):
        if isinstance(valor, str) and valor:
            info[clave] = quitar_fechas_iso(valor)
    return aplicar_lo_publicado(info, [{"tipo": "publicacion", "texto": info.get("acerca") or ""}])


def armar_publicacion(item, profile_url, autor="", tipo_forzado=""):
    """Un tweet ya leído del DOM, sin fechas ISO en el texto visible."""
    item = item or {}
    from app.perfil_redes import quitar_fechas_iso
    texto = quitar_fechas_iso(re.sub(r"\s+", " ", str(item.get("texto") or "")).strip())
    if len(texto) < 15:
        return None
    social = str(item.get("social") or "")
    contexto = str(item.get("contexto") or "")
    if es_repost(social) or es_repost(contexto[:80]):
        tipo = "compartida"
    elif tipo_forzado == "logro":
        tipo = "logro"
    elif es_respuesta(contexto) or item.get("respuesta"):
        tipo = "respuesta"
    else:
        tipo = "publicacion"
    url_post = url_de_publicacion(item.get("href") or "")
    tiempo = tiempo_legible(item.get("etiqueta") or "", item.get("datetime") or "")
    return {
        "perfil": profile_url, "urn": (url_post.rsplit("/", 1)[-1] if url_post else "N/A"),
        "url_publicacion": url_post, "tipo": tipo, "autor": autor,
        "texto": texto, "tiempo": tiempo,
        "hashtags": "", "enlaces": "",
        "respuestas_n": str(item.get("respuestas") or ""),
        "reposts_n": str(item.get("reposts") or ""),
        "me_gusta": str(item.get("me_gusta") or ""),
        "fecha_extraccion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


class XActivityScraper:
    def __init__(self, cookie_file="x_cookies.json",
                 profile_dir="chrome_x_profile", confirmar_login=None):
        self.cookie_file = Path(cookie_file)
        self.profile_dir = Path(profile_dir).resolve()
        self.confirmar_login = confirmar_login
        self.driver = None
        self.info = {}
        self.analisis = LinkedInActivityScraper(
            cookie_file="linkedin_cookies.json", profile_dir="chrome_x_profile")
        self.analisis.prefijo_archivos = "x"
        self.analisis.peso_compartida = self.analisis.peso_propia
        self.analisis.priorizar_propias = False

    def _sanitizar(self, raw):
        if not isinstance(raw, dict) or not raw.get("name") or "value" not in raw:
            return None
        domain = str(raw.get("domain") or ".x.com")
        if "x.com" not in domain and "twitter.com" not in domain:
            return None
        if "twitter.com" in domain:
            domain = ".x.com"
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
        if self.driver is None:
            return False
        return url_pide_login(self.driver.current_url)

    def _tiene_auth_token(self):
        if self.driver is None:
            return False
        try:
            return any(c.get("name") == "auth_token" and c.get("value")
                       for c in self.driver.get_cookies())
        except Exception:
            return False

    def sesion_activa(self):
        # La cookie manda: X a veces deja /login en la dirección un momento
        # después de entrar. Sin cookie, la pantalla de acceso no cuenta.
        if not self._tiene_auth_token():
            return False
        return not self._en_muro_de_login()

    def guardar_cookies(self):
        if self.driver is None:
            return
        try:
            cookies = [c for c in self.driver.get_cookies()
                       if "x.com" in (c.get("domain") or "") or "twitter.com" in (c.get("domain") or "")]
            if "auth_token" not in {c["name"] for c in cookies} and self.cookie_file.is_file():
                try:
                    previas = json.loads(self.cookie_file.read_text(encoding="utf-8"))
                    if isinstance(previas, dict):
                        previas = previas.get("cookies", [])
                    if any(c.get("name") == "auth_token" for c in previas if isinstance(c, dict)):
                        print("Sin sesion activa: conservo las cookies anteriores.")
                        return
                except Exception:
                    pass
            self.cookie_file.write_text(json.dumps(cookies, indent=2, ensure_ascii=False),
                                        encoding="utf-8")
            print(f"Cookies de X guardadas ({len(cookies)})")
        except Exception as e:
            print(f"No se pudieron guardar las cookies: {e}")

    def _ocultar_automatizacion(self):
        """X rechaza el login si Chrome se anuncia como controlado por un programa."""
        try:
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """})
        except Exception:
            pass

    def _cerrar_avisos(self):
        try:
            self.driver.execute_script("""
                const textos = ['aceptar todas las cookies', 'accept all cookies',
                                'allow all cookies', 'ahora no', 'not now'];
                for (const b of document.querySelectorAll('button, [role="button"]')) {
                    const t = (b.innerText || '').trim().toLowerCase();
                    if (textos.includes(t)) b.click();
                }
            """)
        except Exception:
            pass

    def esperar_login_manual(self, contexto=""):
        print("\nX esta pidiendo iniciar sesion. El navegador queda abierto:")
        print("   entra con tu cuenta en esa ventana de Chrome y confirma "
              + ("en la pagina web." if self.confirmar_login else "aqui con Enter."))
        print("   No recargo la pagina hasta que X deje la sesion guardada.")
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
            time.sleep(2)
            if not self._tiene_auth_token():
                print("Aun no se ve la sesion; termina de entrar en esa misma ventana y vuelve a confirmar.")
                continue
            self.driver.get("https://x.com/home")
            time.sleep(4)
            self._cerrar_avisos()
            if self.sesion_activa():
                self.guardar_cookies()
                return True
            print("La cookie esta, pero X sigue en la pantalla de acceso. Termina el codigo o el captcha y confirma otra vez.")

    def iniciar_navegador(self):
        options = Options()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={self.profile_dir}")
        options.add_argument("--window-size=1280,900")
        options.add_argument("--lang=es-ES")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        try:
            self.driver = runtime_nube.crear_driver(options)
        except Exception as e:
            print(f"Chrome no arranco: {e} (¿otro Chrome usa ese perfil?)")
            return False
        self._ocultar_automatizacion()
        self.driver.get("https://x.com/home")
        time.sleep(4)
        self._cerrar_avisos()
        if self.sesion_activa():
            print("Sesion de X activa (perfil de Chrome)")
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
                self.driver.get("https://x.com/home")
                time.sleep(4)
                self._cerrar_avisos()
                if self.sesion_activa():
                    print("Sesion de X activa (cookies)")
                    self.guardar_cookies()
                    return True
            except Exception as e:
                print(f"Cookies de X no utilizables: {e}")
        if not self._en_muro_de_login():
            self.driver.get("https://x.com/i/flow/login")
            time.sleep(3)
        return self.esperar_login_manual("inicio del bot de X")

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

    def _leer_encabezado(self):
        try:
            return self.driver.execute_script("""
                const t = (sel) => {
                    const n = document.querySelector(sel);
                    return n ? (n.innerText || '') : '';
                };
                const cuerpo = (document.body && document.body.innerText) ? document.body.innerText.slice(0, 2500) : '';
                return {
                    nombre: t('[data-testid="UserName"]'),
                    bio: t('[data-testid="UserDescription"]'),
                    ubicacion: t('[data-testid="UserLocation"]'),
                    unio: t('[data-testid="UserJoinDate"]'),
                    profesion: t('[data-testid="UserProfessionalCategory"]'),
                    seguidores: t('a[href$="/verified_followers"], a[href$="/followers"]'),
                    cuerpo: cuerpo,
                    protegida: /protegidas|posts are protected/i.test(cuerpo),
                    ausente: /no existe|doesn.t exist|suspended|suspendida/i.test(cuerpo)
                };
            """) or {}
        except Exception:
            return {}

    def extraer_informacion_perfil(self, profile_url):
        print(f"\nLeyendo primero la ficha de X: {profile_url}")
        self.driver.get(profile_url)
        time.sleep(4)
        self._cerrar_avisos()
        if self._en_muro_de_login():
            if not self.esperar_login_manual(profile_url):
                return {}
            self.driver.get(profile_url)
            time.sleep(4)
        datos = self._leer_encabezado()
        info = parsear_ficha_x(datos)
        info["perfil"] = profile_url
        if info["no_disponible"]:
            print("  X no muestra este perfil.")
        elif info["privado"]:
            print(f"  Cuenta protegida: {info['nombre'] or 'sin nombre'}. Se guarda la ficha visible.")
        else:
            print(f"  OK {info['nombre'] or 'Perfil de X'}"
                  + (f" · {info['seguidores']} seguidores" if info.get("seguidores") else ""))
        self.info = info
        self.analisis.info_perfil[profile_url] = info
        return info

    def _expandir_textos(self):
        try:
            self.driver.execute_script("""
                for (const n of document.querySelectorAll('[data-testid="tweet-text-show-more-link"], [role="button"]')) {
                    const t = (n.innerText || '').trim().toLowerCase();
                    if (t === 'mostrar más' || t === 'show more' || t === 'ver más') n.click();
                }
            """)
        except Exception:
            pass

    def _tweets_visibles(self):
        try:
            return self.driver.execute_script("""
                return [...document.querySelectorAll('article[data-testid="tweet"]')].map(a => {
                    const textos = [...a.querySelectorAll('[data-testid="tweetText"]')]
                        .map(n => n.innerText || '').filter(Boolean);
                    const text = textos.join('\\n');
                    const time = a.querySelector('time');
                    const social = a.querySelector('[data-testid="socialContext"]');
                    const link = a.querySelector('a[href*="/status/"]');
                    const etiqueta = (sel) => {
                        const n = a.querySelector(sel);
                        return n ? (n.getAttribute('aria-label') || n.innerText || '') : '';
                    };
                    return {
                        texto: text,
                        datetime: time ? (time.getAttribute('datetime') || '') : '',
                        etiqueta: time ? (time.innerText || '') : '',
                        social: social ? (social.innerText || '') : '',
                        contexto: (a.innerText || '').slice(0, 280),
                        href: link ? link.href : '',
                        respuesta: /en respuesta a|replying to/i.test(a.innerText || ''),
                        respuestas: etiqueta('[data-testid="reply"]'),
                        reposts: etiqueta('[data-testid="retweet"]'),
                        me_gusta: etiqueta('[data-testid="like"], [data-testid="unlike"]')
                    };
                });
            """) or []
        except Exception:
            return []

    def _recolectar(self, profile_url, tipo_forzado, vistos):
        hoy = datetime.now().date()
        antiguas = 0
        for _ronda in range(6):
            self._expandir_textos()
            time.sleep(0.4)
            for item in self._tweets_visibles():
                post = armar_publicacion(
                    item, profile_url, self.info.get("nombre") or "", tipo_forzado)
                if not post:
                    continue
                clave = post["url_publicacion"] or post["texto"][:80]
                if clave in vistos:
                    continue
                post["hashtags"] = ";".join(self.analisis.extraer_hashtags(post["texto"]))
                post["texto"] = self.analisis._limpiar_texto(post["texto"], limite=2000)
                if len(post["texto"]) < 15:
                    continue
                vistos[clave] = post
                fecha = parse_fecha_publicacion(post.get("tiempo") or "")
                if fecha and (hoy - fecha).days > 365:
                    antiguas += 1
            if antiguas >= 3:
                break
            self.driver.execute_script("window.scrollBy(0, 1400);")
            time.sleep(2)
        return vistos

    def _elegir(self, publicaciones, max_posts):
        """Línea, respuestas y destacados por separado. El repost que encaja con el catálogo no se queda fuera."""
        from app.linkedin_texto import evaluar_publicacion

        def repost_de_catalogo(post):
            if post.get("tipo") != "compartida":
                return False
            ev = evaluar_publicacion(post.get("texto") or "")
            return not ev["omitida"] and bool(ev["intereses"])

        cupo = {"linea": 0, "compartida": 0, "respuesta": 0, "logro": 0}
        elegidas = []
        for post in sorted(publicaciones, key=lambda p: 0 if repost_de_catalogo(p) else 1):
            tipo = post.get("tipo") or "publicacion"
            grupo = tipo if tipo in ("compartida", "respuesta", "logro") else "linea"
            if cupo[grupo] >= max_posts:
                continue
            cupo[grupo] += 1
            elegidas.append(post)
        return elegidas

    def extraer_publicaciones(self, profile_url, max_posts=10):
        if self.info.get("privado") or self.info.get("no_disponible"):
            print("  Sin publicaciones: la cuenta esta protegida o no esta disponible.")
            self.info["interacciones"] = ""
            return []
        base = profile_url.rstrip("/")
        print(f"\nLeyendo publicaciones, respuestas y destacados de {base}")
        vistos = {}
        for ruta, tipo in (
            (base, ""),
            (base + "/with_replies", "respuesta"),
            (base + "/highlights", "logro"),
        ):
            self.driver.get(ruta)
            time.sleep(3)
            self._cerrar_avisos()
            if self._en_muro_de_login():
                if not self.esperar_login_manual(ruta):
                    break
                self.driver.get(ruta)
                time.sleep(3)
            self._recolectar(profile_url, tipo, vistos)
        publicaciones = list(vistos.values())
        vigentes = self._elegir(self.analisis.filtrar_y_ordenar(publicaciones), max_posts)
        self.info = incorporar_datos_importantes(self.info, vigentes)
        self.info["interacciones"] = resumir_interacciones(vigentes)
        self.analisis.info_perfil[profile_url] = self.info
        print(f"  OK {len(vigentes)} dentro del ultimo año "
              f"({self.analisis.ultimas_descartadas} antiguas descartadas, "
              f"{sum(1 for p in vigentes if p.get('tipo') == 'respuesta')} respuestas, "
              f"{sum(1 for p in vigentes if p.get('tipo') == 'compartida')} republicaciones, "
              f"{sum(1 for p in vigentes if p.get('tipo') == 'logro')} destacados)")
        return vigentes

    def ejecutar(self, profile_url, max_posts=10):
        if not self.iniciar_navegador():
            self.cerrar_navegador(preguntar=False)
            return {"ok": False, "motivo": "No se confirmo el inicio de sesion en X."}
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
        description="X: ficha + publicaciones, respuestas y logros del ultimo año")
    parser.add_argument("url", help="https://x.com/usuario")
    parser.add_argument("--max-posts", type=int, default=10)
    args = parser.parse_args()
    bot = XActivityScraper()
    try:
        resultado = bot.ejecutar(args.url, max_posts=args.max_posts)
        print(resultado.get("motivo", "Listo."))
    except Exception as e:
        bot.cerrar_navegador(preguntar=False)
        raise SystemExit(f"Error: {e}") from None
