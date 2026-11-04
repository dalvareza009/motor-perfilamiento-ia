# linkedin_activity_scraper.py
"""
Scraper de actividad de LinkedIn usando TU propia sesión.

Cambios frente a la versión anterior (la que cerraba al pedir login):

1. Sesión persistente doble:
   - Un perfil de Chrome dedicado (``chrome_linkedin_profile/``): Chrome guarda
     ahí la sesión, así que aunque el JSON expire, normalmente sigues dentro.
   - ``linkedin_cookies.json`` como respaldo: se carga al arrancar y, lo más
     importante, SE VUELVE A GUARDAR cada vez que la sesión se confirma, para
     que el ``li_at`` renovado no se pierda.
2. Si LinkedIn pide iniciar sesión, un checkpoint, 2FA o un captcha, el bot
   NO se cierra ni devuelve error: deja el navegador abierto, te avisa y
   espera a que lo resuelvas a mano en esa misma ventana. Al pulsar Enter
   comprueba otra vez y continúa donde iba.
3. Lo mismo si el muro de acceso aparece a mitad de camino (al visitar un
   perfil): pausa, te deja entrar y reintenta esa misma URL.
4. Las cookies se sanean antes de inyectarlas: Selenium rechaza cookies con
   campos de Cookie-Editor/EditThisCookie (``storeId``, ``id``, ``hostOnly``…),
   con ``expiry`` en float o con ``sameSite`` inválido, y una sola cookie mala
   no debe tumbar las demás (sobre todo ``li_at``, que es la de sesión).

Uso:
    python linkedin_activity_scraper.py

La primera vez puede que tengas que iniciar sesión a mano una sola vez.
Las siguientes, el perfil + las cookies guardadas te dejan dentro directo.

IMPORTANTE: ``linkedin_cookies.json`` y ``chrome_linkedin_profile/`` equivalen
a tu sesión abierta. No los subas a git ni los compartas (ya están en
``.gitignore``). Usa solo tu propia cuenta y resuelve a mano cualquier
verificación que LinkedIn te pida; este script no intenta saltársela.
"""
from app import runtime_nube
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import csv
import json
import sys

# La consola de Windows (cp1252) explotaría con los emojis de los print().
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import random
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

# Motor de intereses del proyecto: tema -> producto + razón, y filtro de temas
# sensibles (salario/política/religión no generan recomendación ni se guardan).
try:
    from app.linkedin_texto import evaluar_publicacion, menciona_salario
except Exception:  # el script copiado fuera del proyecto sigue extrayendo, sin recomendar
    evaluar_publicacion = None
    menciona_salario = lambda texto: False

# Marcas de que LinkedIn NO te está dejando pasar con la sesión actual.
MARCAS_MURO = ("/login", "/uas/login", "/signup", "/checkpoint", "authwall")

DIAS_VENTANA = 365  # solo publicaciones del último año
_MESES = {"ene": 1, "enero": 1, "feb": 2, "febrero": 2, "mar": 3, "marzo": 3,
          "abr": 4, "abril": 4, "may": 5, "mayo": 5, "jun": 6, "junio": 6,
          "jul": 7, "julio": 7, "ago": 8, "agosto": 8, "sep": 9, "sept": 9,
          "septiembre": 9, "setiembre": 9, "oct": 10, "octubre": 10,
          "nov": 11, "noviembre": 11, "dic": 12, "diciembre": 12,
          "jan": 1, "apr": 4, "aug": 8, "dec": 12}


def parse_fecha_publicacion(texto, hoy=None):
    """Fecha aproximada desde «21 de may.», «10 de sept. de 2025», «3 sem»…

    Sin año se asume el más reciente que no quede en el futuro. None si no se
    puede interpretar (la publicación se conserva, pero marcada sin verificar).
    """
    hoy = hoy or date.today()
    t = re.sub(r"\s+", " ", str(texto or "").lower()).strip(" .•·")
    if not t:
        return None
    if t in ("ahora", "justo ahora", "now"):
        return hoy
    if t == "ayer":
        return hoy - timedelta(days=1)
    rel = re.match(r"(\d+)\s*(h|hora|horas|min|minuto|minutos|d|día|dias|día|sem|semana|semanas|mes|meses|año|años|yr|yrs|w|mo)\b", t)
    if rel:
        n, unidad = int(rel.group(1)), rel.group(2)
        dias = {"h": 0, "hora": 0, "horas": 0, "min": 0, "minuto": 0, "minutos": 0,
                "d": 1, "día": 1, "dias": 1, "sem": 7, "semana": 7, "semanas": 7, "w": 7,
                "mes": 30, "meses": 30, "mo": 30, "año": 365, "años": 365, "yr": 365, "yrs": 365}[unidad]
        return hoy - timedelta(days=n * dias)
    m = re.search(r"(\d{1,2}) de ([a-záéí]+)\.?(?: de (\d{4}))?", t)
    if m and m.group(2).strip(".") in _MESES:
        dia, mes = int(m.group(1)), _MESES[m.group(2).strip(".")]
        if m.group(3):
            try:
                return date(int(m.group(3)), mes, dia)
            except ValueError:
                return None
        try:
            candidata = date(hoy.year, mes, dia)
        except ValueError:
            return None
        return candidata if candidata <= hoy else date(hoy.year - 1, mes, dia)
    m = re.search(r"([a-z]+)\.? (\d{1,2}),? (\d{4})", t)  # May 21, 2026
    if m and m.group(1) in _MESES:
        try:
            return date(int(m.group(3)), _MESES[m.group(1)], int(m.group(2)))
        except ValueError:
            return None
    iso = re.fullmatch(
        r"(\d{4})-(\d{2})-(\d{2})(?:t\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:z|[+-]\d{2}:?\d{2})?)?", t)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None
    return None


class LinkedInActivityScraper:
    def __init__(self, cookie_file='linkedin_cookies.json',
                 profile_dir='chrome_linkedin_profile', confirmar_login=None):
        self.cookie_file = Path(cookie_file)
        # Perfil dedicado: NO uses tu perfil normal de Chrome (estaría bloqueado
        # si tienes Chrome abierto) ni lo borres entre ejecuciones.
        self.profile_dir = Path(profile_dir).resolve()
        # Desde la web no hay consola: quien lanza el bot pasa un callable que
        # bloquea hasta que el usuario pulsa «Ya inicié sesión» en el navegador.
        self.confirmar_login = confirmar_login
        self.driver = None
        self.resultados = []          # publicaciones aptas (sin temas sensibles)
        self.recomendaciones = []     # una fila por perfil + producto
        self.resumen = {}             # perfil -> conteos, temas y recomendaciones
        self.omitidas_sensibles = Counter()
        self.descartadas_antiguas = 0
        self.ultimas_descartadas = 0
        self.info_perfil = {}         # url -> ficha del perfil (se lee ANTES que la actividad)
        self.prefijo_archivos = "linkedin"
        # Pesos de evidencia: la ficha manda. En LinkedIn la propia pesa más
        # que la compartida; Facebook iguala ambas (ver facebook_activity_scraper).
        self.peso_perfil = 5
        self.peso_propia = 3
        self.peso_compartida = 1
        self.priorizar_propias = True
        self._analizado = False

    # ---------- Utilidades ----------
    def gaussian_delay(self, mean=3.0, std=1.2):
        """Retardo gaussiano para simular comportamiento humano."""
        u1 = random.random() or 1e-9
        u2 = random.random()
        z0 = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
        return max(0.5, z0 * std + mean)

    # ---------- Cookies ----------
    @staticmethod
    def _sanitizar_cookie(raw):
        """Deja una cookie tal y como la acepta Selenium, o None si no sirve.

        Acepta el formato de Cookie-Editor / EditThisCookie y el de
        ``driver.get_cookies()``. Solo pasan cookies de LinkedIn.
        """
        if not isinstance(raw, dict) or not raw.get("name") or "value" not in raw:
            return None
        domain = str(raw.get("domain") or ".linkedin.com")
        if "linkedin.com" not in domain:
            return None
        cookie = {
            "name": str(raw["name"]),
            "value": str(raw["value"]),
            "domain": domain,
            "path": str(raw.get("path") or "/"),
            "secure": bool(raw.get("secure", True)),
            "httpOnly": bool(raw.get("httpOnly", False)),
        }
        # Selenium exige int; Cookie-Editor lo exporta a veces como float.
        expiry = raw.get("expiry", raw.get("expirationDate"))
        if isinstance(expiry, (int, float)) and expiry > 0:
            cookie["expiry"] = int(expiry)
        # Solo estos tres valores son válidos; cualquier otro tumbaba la cookie.
        if raw.get("sameSite") in ("Strict", "Lax", "None"):
            cookie["sameSite"] = raw["sameSite"]
        return cookie

    def cargar_cookies_desde_archivo(self):
        """Inyecta las cookies del JSON. Devuelve cuántas entraron."""
        if not self.cookie_file.is_file():
            print(f"ℹ Sin {self.cookie_file}: se usará el perfil de Chrome "
                  "o el inicio de sesión manual.")
            return 0
        try:
            datos = json.loads(self.cookie_file.read_text(encoding='utf-8'))
        except Exception as e:
            print(f"⚠ No se pudo leer {self.cookie_file}: {e}")
            return 0
        # Formatos habituales: lista, {"cookies": [...]} o {nombre: valor}.
        if isinstance(datos, dict) and isinstance(datos.get("cookies"), list):
            datos = datos["cookies"]
        if isinstance(datos, dict):
            datos = [{"name": k, "value": v, "domain": ".linkedin.com"}
                     for k, v in datos.items()]
        if not isinstance(datos, list):
            print("⚠ El archivo de cookies no tiene un formato reconocible.")
            return 0

        cargadas, tiene_li_at = 0, False
        for raw in datos:
            cookie = self._sanitizar_cookie(raw)
            if not cookie:
                continue
            try:
                self.driver.add_cookie(cookie)
                cargadas += 1
                tiene_li_at = tiene_li_at or cookie["name"] == "li_at"
            except Exception:
                continue  # una cookie mala no debe tumbar al resto
        if cargadas and not tiene_li_at:
            print("⚠ Las cookies cargadas no incluyen 'li_at', que es la cookie "
                  "de sesión: probablemente tendrás que entrar a mano.")
        print(f"✅ {cargadas} cookies inyectadas desde {self.cookie_file}")
        return cargadas

    def guardar_cookies(self):
        """Guarda las cookies actuales (con el li_at ya renovado) en el JSON."""
        if self.driver is None:
            return
        try:
            cookies = [c for c in self.driver.get_cookies()
                       if "linkedin.com" in (c.get("domain") or "")]
            self.cookie_file.write_text(
                json.dumps(cookies, indent=2, ensure_ascii=False),
                encoding='utf-8')
            print(f"💾 Cookies actualizadas guardadas en {self.cookie_file} "
                  f"({len(cookies)} cookies)")
        except Exception as e:
            print(f"⚠ No se pudieron guardar las cookies: {e}")

    # ---------- Sesión ----------
    def _es_muro(self):
        url = (self.driver.current_url or "").lower()
        if any(m in url for m in MARCAS_MURO):
            return True
        try:
            fuente = (self.driver.page_source or "").lower()
        except Exception:
            return False
        return "authwall" in fuente

    def sesion_activa(self):
        """True si LinkedIn te reconoce: hay li_at y se ve la barra global."""
        if self._es_muro():
            return False
        try:
            nombres = {c["name"] for c in self.driver.get_cookies()}
            if "li_at" not in nombres:
                return False
            return bool(self.driver.find_elements(
                By.CSS_SELECTOR,
                "header.global-nav, .global-nav, a[href*='/feed/'], "
                "input[placeholder*='Buscar'], input[placeholder*='Search']"))
        except Exception:
            return False

    def _esperar_resolucion(self, segundos=15):
        """Espera a que la página sea 'o sesión o muro', lo primero que llegue."""
        def resuelto(d):
            return self.sesion_activa() or self._es_muro()
        try:
            WebDriverWait(self.driver, segundos).until(resuelto)
        except TimeoutException:
            pass

    def esperar_login_manual(self, contexto=""):
        """
        LA CLAVE: si LinkedIn pide login/checkpoint/2FA, NO se cierra nada.

        Deja el navegador abierto para que inicies sesión tú mismo en esa
        ventana y espera tu Enter. Devuelve True si al final hay sesión.
        """
        print("\n" + "=" * 60)
        print("🔐 LinkedIn está pidiendo iniciar sesión o una verificación.")
        if contexto:
            print(f"   Pasó en: {contexto}")
        print("   1. Inicia sesión TÚ en la ventana de Chrome que quedó abierta")
        print("      (usuario, contraseña, código 2FA o captcha si lo pide).")
        print("   2. Cuando veas tu feed/perfil cargado, confirma para seguir "
              + ("en la página web." if self.confirmar_login is not None else "aquí."))
        if self.confirmar_login is None:
            print("   Escribe 'salir' + Enter si prefieres abortar.")
        print("=" * 60)
        if not runtime_nube.login_manual_permitido():
            print("En el servidor no hay login manual: hace falta una cookie de sesión vigente.")
            return False
        while True:
            if self.confirmar_login is not None:
                # Modo web: la espera la resuelve el front, no el teclado.
                if self.confirmar_login(contexto) != "continuar":
                    return False
            else:
                try:
                    respuesta = input("⏎ Pulsa Enter cuando ya hayas entrado "
                                      "(o 'salir'): ").strip().lower()
                except EOFError:
                    print("⚠ Sin consola interactiva: no puedo esperar el login manual.")
                    return False
                if respuesta in ("salir", "exit", "q", "quit"):
                    return False
            self.driver.get("https://www.linkedin.com/feed/")
            time.sleep(self.gaussian_delay(3, 1))
            self._esperar_resolucion()
            if self.sesion_activa():
                print("✅ Sesión activa. Guardando cookies renovadas…")
                self.guardar_cookies()
                return True
            print("… Aún no se ve la sesión (¿falta el código o el captcha?). "
                  "Termina de entrar en Chrome y vuelve a pulsar Enter.")

    def iniciar_navegador(self):
        options = Options()
        # Perfil persistente: aquí vive la sesión entre ejecuciones.
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={self.profile_dir}")
        options.add_argument('--window-size=1280,900')
        options.add_argument('--lang=es-ES')
        options.add_argument('--disable-notifications')

        try:
            self.driver = runtime_nube.crear_driver(options)
        except Exception as e:
            print(f"❌ Chrome no arrancó: {e}")
            print("   Suele ser porque otro Chrome está usando ese mismo "
                  f"perfil ({self.profile_dir}). Ciérralo y reintenta.")
            return False

        # 1) El perfil dedicado ya puede traer la sesión de la vez anterior.
        self.driver.get("https://www.linkedin.com/feed/")
        time.sleep(self.gaussian_delay(3, 1))
        self._esperar_resolucion()
        if self.sesion_activa():
            print("✅ Sesión activa (perfil de Chrome)")
            self.guardar_cookies()
            return True

        # 2) Si no, se inyectan las cookies del JSON (hay que estar ya en el
        #    dominio de LinkedIn para poder añadirlas, por eso es el paso 2).
        if self.cargar_cookies_desde_archivo():
            self.driver.get("https://www.linkedin.com/feed/")
            time.sleep(self.gaussian_delay(3, 1))
            self._esperar_resolucion()
            if self.sesion_activa():
                print("✅ Sesión activa (cookies del archivo)")
                self.guardar_cookies()
                return True
            print("⚠ Las cookies no abrieron sesión (expiradas o revocadas).")

        # 3) Antes aquí se cerraba todo. Ahora: navegador abierto y a entrar.
        return self.esperar_login_manual("inicio del bot")

    def asegurar_sesion(self, url_destino, contexto=""):
        """Si apareció el muro a mitad de camino, pausa, deja entrar y reintenta."""
        for intento in range(3):
            if not self._es_muro():
                return True
            print(f"⚠ Muro de acceso en {contexto or url_destino}. "
                  "El navegador sigue abierto, no se pierde la sesión.")
            if not self.esperar_login_manual(contexto or url_destino):
                return False
            self.driver.get(url_destino)
            time.sleep(self.gaussian_delay(3, 1))
            self._esperar_resolucion()
        return not self._es_muro()

    def cerrar_navegador(self, preguntar=True):
        if self.driver is None:
            return
        self.guardar_cookies()
        if preguntar:  # desde la web no hay nadie en la consola del servidor
            try:
                input("\nPulsa Enter para cerrar el navegador… ")
            except EOFError:
                pass
        try:
            self.driver.quit()
        except Exception:
            pass
        self.driver = None

    # ---------- Localización robusta (sin IDs dinámicas) ----------
    def obtener_contenedor_publicaciones(self):
        intentos = [
            # Estructura nueva (SDUI): la lista ya no usa data-urn ni clases de
            # feed; se ancla en data-testid / LazyColumn, que sí son estables.
            (By.CSS_SELECTOR, "[data-testid^='ProfileRecentActivityAll']"),
            (By.CSS_SELECTOR, "[data-component-type='LazyColumn']"),
            (By.XPATH, "//div[contains(@class,'scaffold-finite-scroll__content')]"),
            (By.XPATH, "//div[contains(@class,'profile-creator-shared-feed-update__container')]"),
            (By.XPATH, "//section[.//div[@data-urn]]"),
            (By.XPATH, "//main"),
        ]
        for by, xpath in intentos:
            try:
                contenedor = WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located((by, xpath))
                )
                print(f"  ✔ Contenedor localizado con: {xpath[:60]}...")
                return contenedor
            except TimeoutException:
                continue
        print("  ⚠ No se pudo localizar un contenedor de publicaciones")
        return None

    def obtener_publicaciones(self, contenedor):
        selectores = [
            # Estructura nueva: cada publicación es un listitem update-card.
            ".//div[@role='listitem' and starts-with(@componentkey,'update-card')]",
            ".//div[@role='listitem'][.//*[@data-testid='expandable-text-box']]",
            ".//div[@data-urn]",
            ".//li[@data-urn]",
            ".//article",
            ".//div[contains(@class,'feed-shared-update-v2')]",
            ".//li[contains(@class,'profile-creator-shared-feed-update')]",
        ]
        for sel in selectores:
            try:
                posts = contenedor.find_elements(By.XPATH, sel)
                if posts:
                    print(f"  ✔ {len(posts)} publicaciones con selector: {sel}")
                    return posts
            except Exception:
                continue
        print("  ⚠ No se encontraron publicaciones con ningún selector")
        return []

    def scroll_progresivo(self, n_scrolls=3, px=800):
        for _ in range(n_scrolls):
            self.driver.execute_script(f"window.scrollBy(0, {px});")
            time.sleep(self.gaussian_delay(1.5, 0.5))

    # ---------- Extracción de una publicación ----------
    _LINEAS_UI = {"ver más", "see more", "… más", "... más", "ver menos", "see less",
                  "recomendar", "comentar", "compartir", "enviar", "like", "comment", "share"}

    def _limpiar_texto(self, texto, limite=2000):
        """Quita botones de la interfaz, fechas ISO y líneas repetidas; deja el contenido."""
        from app.perfil_redes import quitar_fechas_iso
        vistas, limpias = set(), []
        for linea in str(texto or "").splitlines():
            linea = quitar_fechas_iso(re.sub(r"\s+", " ", linea).strip())
            clave = linea.lower()
            if not linea or clave in self._LINEAS_UI or clave in vistas:
                continue
            vistas.add(clave)
            limpias.append(linea)
        return "\n".join(limpias)[:limite].strip()

    def expandir_texto(self, post):
        """Pulsa 'ver más' si existe, para no analizar un texto cortado a la mitad."""
        try:
            for boton in post.find_elements(By.CSS_SELECTOR, "button")[:12]:
                if (boton.text or "").strip().lower() in self._LINEAS_UI - {"recomendar", "comentar", "compartir", "enviar", "like", "comment", "share"}:
                    self.driver.execute_script("arguments[0].click();", boton)
                    time.sleep(0.4)
                    return
        except Exception:
            pass

    def extraer_texto_publicacion(self, post):
        """Texto completo (hasta 2000 caracteres, como el motor de intereses)."""
        self.expandir_texto(post)
        selectores = [
            "[data-testid='expandable-text-box']",
            "div.update-components-text span.break-words",
            "div.feed-shared-update-v2__description span.break-words",
            "span.break-words",
            "div.feed-shared-text",
            "div.update-components-text",
        ]
        for sel in selectores:
            try:
                elem = post.find_element(By.CSS_SELECTOR, sel)
                texto = self._limpiar_texto(elem.text)
                if len(texto) > 5:
                    return texto
            except NoSuchElementException:
                continue
        # Fallback: texto completo del post, ya limpio de botones.
        try:
            return self._limpiar_texto(post.text)
        except Exception:
            return ""

    def extraer_autor(self, post):
        # Estructura nueva: el autor original sale del menú de la publicación
        # («Abrir el menú de controles para la publicación de X»).
        try:
            for el in post.find_elements(By.CSS_SELECTOR, "[aria-label]")[:20]:
                etiqueta = el.get_attribute("aria-label") or ""
                marca = "para la publicación de "
                if marca in etiqueta:
                    return etiqueta.split(marca, 1)[1].strip()[:120]
        except Exception:
            pass
        for sel in ("span.update-components-actor__name span[aria-hidden='true']",
                    "span.feed-shared-actor__name span[aria-hidden='true']",
                    "span.update-components-actor__name",
                    "span.feed-shared-actor__name"):
            try:
                txt = post.find_element(By.CSS_SELECTOR, sel).text.strip()
                if txt:
                    return txt.splitlines()[0][:120]
            except NoSuchElementException:
                continue
        return ""

    def extraer_hashtags(self, texto):
        return list(dict.fromkeys(re.findall(r"#[\wáéíóúñü]+", texto or "", flags=re.I)))

    def extraer_enlaces(self, post):
        enlaces = []
        try:
            for a in post.find_elements(By.CSS_SELECTOR, "a[href]"):
                href = (a.get_attribute("href") or "").strip()
                if href.startswith("http") and "linkedin.com" not in href and href not in enlaces:
                    enlaces.append(href)
                if len(enlaces) >= 5:
                    break
        except Exception:
            pass
        return enlaces

    def extraer_metricas(self, post):
        """(reacciones, comentarios) desde los aria-label, '' si LinkedIn no los muestra."""
        etiquetas = []
        try:
            for el in post.find_elements(By.CSS_SELECTOR, "[aria-label]")[:30]:
                etiquetas.append(el.get_attribute("aria-label") or "")
        except Exception:
            pass
        junto = " ".join(etiquetas)
        reac = re.search(r"(\d[\d.,]*)\s*(?:reacciones|reactions|me gusta|likes)", junto, re.I)
        com = re.search(r"(\d[\d.,]*)\s*(?:comentarios|comments)", junto, re.I)
        return (reac.group(1) if reac else "", com.group(1) if com else "")

    @staticmethod
    def url_desde_urn(urn):
        if urn and ("urn:li:activity:" in urn or "urn:li:ugcPost:" in urn or "urn:li:share:" in urn):
            return f"https://www.linkedin.com/feed/update/{urn.strip()}/"
        return ""

    def extraer_tiempo_publicacion(self, post):
        selectores = [
            "span.feed-shared-actor__sub-description",
            "span.update-components-actor__sub-description",
            "span[class*='sub-description']",
            "time",
        ]
        for sel in selectores:
            try:
                elem = post.find_element(By.CSS_SELECTOR, sel)
                txt = elem.text.strip()
                if txt:
                    return txt
            except NoSuchElementException:
                continue
        # Estructura nueva: la fecha va como una línea suelta («21 de may.»,
        # «30 de ene.», «6 de oct. de 2025») entre las primeras del post.
        try:
            patron = re.compile(r"^(\d{1,2} de \w+\.(?: de \d{4})?|\d+\s*(?:h|d|sem|mes|año)s?\.?)$", re.I)
            for linea in (post.text or "").splitlines()[:15]:
                if patron.match(linea.strip()):
                    return linea.strip()
        except Exception:
            pass
        return "N/A"

    @staticmethod
    def _urn_de_href(href):
        hallado = re.search(r"(urn:li:(?:activity|ugcPost|share):\d+)", href or "")
        return hallado.group(1) if hallado else ""

    def extraer_urn(self, post):
        try:
            urn = post.get_attribute("data-urn")
            if urn:
                return urn
            # Estructura nueva: sin data-urn, pero a veces hay enlace al post.
            for a in post.find_elements(By.CSS_SELECTOR, "a[href*='/feed/update/']")[:5]:
                urn = self._urn_de_href(a.get_attribute("href"))
                if urn:
                    return urn
        except Exception:
            pass
        return "N/A"

    # ---------- Ventana de un año y priorización ----------
    def filtrar_y_ordenar(self, publicaciones, hoy=None, dias=DIAS_VENTANA):
        """Deja solo el último año y ordena: propias recientes primero.

        Completa fecha_publicacion/antiguedad_dias de cada publicación.
        Las de fecha no interpretable se conservan (marcadas), porque la
        actividad viene ordenada de reciente a antigua; las que SÍ tienen
        fecha y superan la ventana se descartan y se cuentan.
        """
        hoy = hoy or date.today()
        vigentes, descartadas = [], 0
        for post in publicaciones:
            fecha = parse_fecha_publicacion(post.get("tiempo", ""), hoy)
            post["fecha_publicacion"] = fecha.isoformat() if fecha else ""
            post["antiguedad_dias"] = (hoy - fecha).days if fecha else ""
            if fecha and (hoy - fecha).days > dias:
                descartadas += 1
                continue
            vigentes.append(post)
        self.descartadas_antiguas += descartadas
        self.ultimas_descartadas = descartadas
        vigentes.sort(key=lambda p: (
            (1 if p.get("tipo") == "compartida" else 0) if self.priorizar_propias else 0,
            p["antiguedad_dias"] if p["antiguedad_dias"] != "" else 366,
            -(len(p.get("texto", "")))))
        return vigentes

    # ---------- Ficha del perfil (se lee ANTES que las publicaciones) ----------
    def extraer_informacion_perfil(self, profile_url):
        """Nombre, titular, ubicación y secciones Acerca/Experiencia/Educación."""
        if not profile_url.endswith('/'):
            profile_url += '/'
        print(f"\n👤 Leyendo primero la ficha del perfil: {profile_url}")
        self.driver.get(profile_url)
        time.sleep(self.gaussian_delay(4, 1.5))
        if not self.asegurar_sesion(profile_url, contexto=profile_url):
            return {}
        self.scroll_progresivo(n_scrolls=2, px=700)

        info = {"perfil": profile_url, "nombre": "", "titular": "", "ubicacion": "",
                "acerca": "", "experiencia": "", "educacion": "", "seguidores": ""}
        try:
            info["nombre"] = self.driver.find_element(By.TAG_NAME, "h1").text.strip().splitlines()[0][:120]
        except Exception:
            pass
        for sel in ("div.text-body-medium.break-words", "div[class*='headline']"):
            try:
                txt = self.driver.find_element(By.CSS_SELECTOR, sel).text.strip()
                if txt:
                    info["titular"] = txt.splitlines()[0][:300]
                    break
            except Exception:
                continue
        # Secciones por su encabezado (sirve en la interfaz clásica y la nueva).
        claves = {"acerca de": "acerca", "acerca": "acerca", "about": "acerca",
                  "experiencia": "experiencia", "experience": "experiencia",
                  "educación": "educacion", "educacion": "educacion", "education": "educacion"}
        try:
            for h2 in self.driver.find_elements(By.TAG_NAME, "h2")[:30]:
                destino = claves.get((h2.text or "").strip().lower())
                if not destino or info[destino]:
                    continue
                texto = self.driver.execute_script(
                    "let n=arguments[0]; for(let i=0;i<6&&n;i++){ n=n.parentElement;"
                    " if(n && n.innerText && n.innerText.length>80) return n.innerText; } return '';",
                    h2)
                if texto:
                    info[destino] = self._limpiar_texto(texto, limite=1500)
        except Exception:
            pass
        try:
            cuerpo = self.driver.find_element(By.TAG_NAME, "body").text
            m = re.search(r"([\d.,]+)\s*(?:seguidores|followers)", cuerpo, re.I)
            if m:
                info["seguidores"] = m.group(1)
            # Respaldo SDUI: si h1/titular no aparecieron, salen del título de
            # la pestaña («Nombre | LinkedIn») y de la línea siguiente al nombre.
            if not info["nombre"]:
                titulo = (self.driver.title or "").split("|")[0].strip()
                if titulo and "linkedin" not in titulo.lower():
                    info["nombre"] = titulo[:120]
            if info["nombre"] and not info["titular"]:
                lineas = [l.strip() for l in cuerpo.splitlines() if l.strip()]
                for i, linea in enumerate(lineas):
                    if linea == info["nombre"] and i + 1 < len(lineas):
                        candidata = lineas[i + 1]
                        if candidata.lower() not in ("conectar", "seguir", "enviar mensaje"):
                            info["titular"] = candidata[:300]
                        break
        except Exception:
            pass
        # Experiencia/Educación no siempre se renderizan en la portada del
        # perfil: LinkedIn las sirve completas en sus subpáginas /details/…
        for destino, ruta in (("experiencia", "details/experience/"),
                              ("educacion", "details/education/")):
            if info[destino]:
                continue
            try:
                self.driver.get(profile_url + ruta)
                time.sleep(self.gaussian_delay(2.5, 0.8))
                principal = self.driver.find_element(By.TAG_NAME, "main").text
                if len(principal) > 60:
                    info[destino] = self._limpiar_texto(principal, limite=1500)
            except Exception:
                continue
        from app.perfil_redes import quitar_fechas_iso
        for clave, valor in list(info.items()):
            if isinstance(valor, str) and valor and clave != "perfil":
                info[clave] = quitar_fechas_iso(valor)
        self.info_perfil[profile_url] = info
        print(f"  ✔ {info['nombre'] or 'Perfil'} · {info['titular'][:70]}")
        return info

    # ---------- Flujo principal de extracción ----------
    def extraer_publicaciones_perfil(self, profile_url, max_posts=10):
        if not profile_url.endswith('/'):
            profile_url += '/'
        activity_url = profile_url + "recent-activity/all/"

        print(f"\n📄 Visitando: {activity_url}")
        self.driver.get(activity_url)
        time.sleep(self.gaussian_delay(4, 1.5))

        # Si aquí LinkedIn levanta el muro, no se aborta el perfil en silencio:
        # se pausa, entras a mano y se reintenta ESTA misma URL.
        if not self.asegurar_sesion(activity_url, contexto=activity_url):
            print("  ⚠ Sin sesión tras el intento manual: se salta este perfil, "
                  "pero el navegador sigue abierto.")
            return []

        # LinkedIn lo dice tal cual cuando el perfil no tiene actividad visible:
        # no es un fallo de selectores, es que no hay nada que extraer.
        try:
            texto_pagina = self.driver.find_element(By.TAG_NAME, "body").text.lower()
        except Exception:
            texto_pagina = ""
        if any(f in texto_pagina for f in ("no hay actividad en este momento",
                                           "no recent activity", "nothing to see here")):
            print("  ℹ LinkedIn muestra «No hay actividad en este momento»: "
                  "este perfil no tiene actividad visible que extraer.")
            return []

        contenedor = self.obtener_contenedor_publicaciones() or self.driver
        # La lista nueva monta las tarjetas con retraso: sin esta espera, el
        # primer barrido puede llegar antes que las publicaciones.
        try:
            WebDriverWait(self.driver, 10).until(lambda d: d.find_elements(
                By.CSS_SELECTOR,
                "[data-testid='expandable-text-box'], [data-urn], "
                "div[role='listitem'][componentkey^='update-card']"))
        except TimeoutException:
            pass
        publicaciones, vistos = [], set()
        # Se recoge tras cada scroll: el lazy-load va añadiendo publicaciones
        # y un único barrido al final se dejaba las primeras por el camino.
        for ronda in range(4):
            posts = self.obtener_publicaciones(contenedor)
            for post in posts:
                try:
                    urn = self.extraer_urn(post)
                    texto = self.extraer_texto_publicacion(post)
                    if len(texto) < 5:
                        continue
                    clave = urn if urn != "N/A" else re.sub(r"\s+", " ", texto.lower())[:200]
                    if clave in vistos:
                        continue
                    vistos.add(clave)
                    reacciones, comentarios = self.extraer_metricas(post)
                    try:
                        cabecera = (post.text or "")[:400].lower()
                    except Exception:
                        cabecera = ""
                    es_compartida = "han compartido esto" in cabecera or "ha compartido esto" in cabecera
                    publicaciones.append({
                        'perfil': profile_url,
                        'urn': urn,
                        'url_publicacion': self.url_desde_urn(urn),
                        'tipo': 'compartida' if es_compartida else (
                            'publicacion' if ('activity' in urn or 'ugcPost' in urn
                                              or 'share' in urn) else 'actividad'),
                        'autor': self.extraer_autor(post),
                        'texto': texto,
                        'tiempo': self.extraer_tiempo_publicacion(post),
                        'hashtags': ";".join(self.extraer_hashtags(texto)),
                        'enlaces': ";".join(self.extraer_enlaces(post)),
                        'reacciones': reacciones,
                        'comentarios': comentarios,
                        'fecha_extraccion': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    print(f"  📝 [{len(publicaciones)}] {texto[:60]}...")
                    if len(publicaciones) >= max_posts:
                        break
                except Exception as e:
                    print(f"  ⚠ Error en una publicación: {e}")
                    continue
            if len(publicaciones) >= max_posts:
                break
            self.scroll_progresivo(n_scrolls=1)
            # El scroll también puede disparar el muro: pausa y reintento.
            if self._es_muro() and not self.asegurar_sesion(activity_url, contexto=activity_url):
                break

        vigentes = self.filtrar_y_ordenar(publicaciones)
        if self.ultimas_descartadas:
            print(f"  🗓 {self.ultimas_descartadas} publicación(es) de hace más de "
                  f"un año quedaron fuera de la ventana.")
        propias = sum(1 for p in vigentes if p["tipo"] != "compartida")
        print(f"  ✔ {len(vigentes)} dentro del último año "
              f"({propias} propias, {len(vigentes) - propias} compartidas)")
        return vigentes[:max_posts]

    # ---------- De actividad a recomendaciones ----------
    def analizar_publicaciones(self, publicaciones):
        """
        Aplica el motor del proyecto (`app.linkedin_texto.evaluar_publicacion`).

        - Lo sensible (salario/política/religión) se cuenta como omitido y su
          texto NO pasa ni a resultados ni a recomendaciones.
        - Agrupa por perfil + producto: la puntuación es en cuántas
          publicaciones distintas aparece el tema. Así la recomendación sale
          ordenada por fuerza de la evidencia, no por orden de aparición.
        Devuelve las publicaciones aptas.
        """
        self.recomendaciones, self.resumen = [], {}
        self.omitidas_sensibles = Counter()
        if evaluar_publicacion is None:
            print("⚠ No se encontró app.linkedin_texto: se extrae actividad, "
                  "pero no se generan recomendaciones.")
            self.resultados = list(publicaciones)
            return self.resultados

        aptas, detalle = [], defaultdict(list)   # (perfil, producto) -> evidencias
        temas_por_perfil = defaultdict(Counter)
        temas_perfil = defaultdict(Counter)

        # 1) PRIMERO la ficha: lo que el perfil dice de sí mismo pesa más que
        #    cualquier publicación (y mucho más que una compartida).
        for url, info in self.info_perfil.items():
            for seccion in ("titular", "acerca", "experiencia", "educacion", "estado_civil"):
                texto = info.get(seccion) or ""
                if len(texto) < 20:
                    continue
                evaluacion = evaluar_publicacion(texto)
                if evaluacion["omitida"]:
                    continue
                if evaluacion.get("salario"):
                    # El salario cuenta: queda como tema de ingresos de la ficha.
                    temas_perfil[url]["ingresos"] += 1
                    temas_por_perfil[url]["ingresos"] += 1
                for interes in evaluacion["intereses"]:
                    temas_perfil[url][interes["tema"]] += 1
                    temas_por_perfil[url][interes["tema"]] += 1
                    detalle[(url, interes["producto"])].append({
                        'tema': interes["tema"], 'razon': interes["razon"],
                        'origen': f"perfil:{seccion}", 'peso': self.peso_perfil,
                        'urn': "", 'url_publicacion': url, 'tiempo': "",
                        'extracto': re.sub(r"\s+", " ", texto)[:300],
                    })

        # 2) DESPUÉS las publicaciones, ya filtradas al último año y ordenadas
        #    (propias recientes primero). Relevancia = tema del catálogo +
        #    autoría + recencia; sin tema, la publicación no construye perfil.
        for post in publicaciones:
            evaluacion = evaluar_publicacion(post.get("texto", ""))
            if evaluacion["omitida"]:
                self.omitidas_sensibles[evaluacion["motivo"]] += 1
                continue
            intereses = evaluacion["intereses"]
            con_salario = bool(evaluacion.get("salario"))
            if con_salario:
                temas_por_perfil[post["perfil"]]["ingresos"] += 1
            relevante = bool(intereses) or con_salario
            propia = post.get("tipo") != "compartida"
            antiguedad = post.get("antiguedad_dias")
            bonus = 2 if isinstance(antiguedad, int) and antiguedad <= 90 else \
                1 if isinstance(antiguedad, int) and antiguedad <= 180 else 0
            # En LinkedIn la compartida pesa menos; en Facebook pesa igual
            # (peso_compartida == peso_propia), porque ahí compartir ES la
            # forma habitual de publicar.
            peso = ((self.peso_propia if propia else self.peso_compartida) + bonus) if relevante else 0
            post["relevancia"] = ("alta" if relevante and (propia or not self.priorizar_propias) else
                                  "media" if relevante else "baja")
            motivos_tema = ["tema:" + i["tema"] for i in intereses]
            if con_salario:
                motivos_tema.append("tema:ingresos")
            post["motivos_relevancia"] = ";".join(
                (motivos_tema if motivos_tema else ["sin tema del catálogo"])
                + (["publicación propia"] if propia else
                   ["compartida: señal más débil" if self.peso_compartida < self.peso_propia
                    else "compartida"])
                + ([f"hace {antiguedad} días"] if isinstance(antiguedad, int) else ["fecha sin verificar"]))
            aptas.append(post)
            ya_peso = set()
            for interes in intereses:
                temas_por_perfil[post["perfil"]][interes["tema"]] += 1
                clave_peso = (post["perfil"], interes["producto"])
                detalle[(post["perfil"], interes["producto"])].append({
                    'tema': interes["tema"],
                    'razon': interes["razon"],
                    'origen': f"publicacion:{post.get('tipo', '')}",
                    'peso': 0 if clave_peso in ya_peso else peso,
                    'urn': post.get("urn", ""),
                    'url_publicacion': post.get("url_publicacion", ""),
                    'tiempo': post.get("tiempo", ""),
                    'extracto': re.sub(r"\s+", " ", post.get("texto", ""))[:300],
                })
                ya_peso.add(clave_peso)

        for (perfil, producto), evidencias in detalle.items():
            urns = {e["urn"] for e in evidencias if e["urn"]}
            de_perfil = sum(1 for e in evidencias if e["origen"].startswith("perfil:"))
            self.recomendaciones.append({
                'perfil': perfil,
                'producto': producto,
                'temas': ";".join(sorted({e["tema"] for e in evidencias})),
                'publicaciones_que_apoyan': len(urns) or sum(
                    1 for e in evidencias if e["origen"].startswith("publicacion:")),
                'puntuacion': sum(e["peso"] for e in evidencias),
                'razones': " | ".join(dict.fromkeys(e["razon"] for e in evidencias)),
                'evidencias': evidencias,
                'desde_el_perfil': de_perfil > 0,
            })
        self.recomendaciones.sort(key=lambda r: (-r["puntuacion"], r["producto"]))
        self._analizado = True

        perfiles_todos = {p["perfil"] for p in publicaciones} | set(self.info_perfil)
        for perfil in perfiles_todos:
            recs = [r for r in self.recomendaciones if r["perfil"] == perfil]
            self.resumen[perfil] = {
                'perfil_info': self.info_perfil.get(perfil, {}),
                'temas_del_perfil': dict(temas_perfil[perfil]),
                'descartadas_por_antiguas': self.descartadas_antiguas,
                'publicaciones_extraidas': sum(1 for p in publicaciones if p["perfil"] == perfil),
                'publicaciones_aptas': sum(1 for p in aptas if p["perfil"] == perfil),
                'omitidas_sensibles': sum(1 for p in publicaciones if p["perfil"] == perfil) - sum(1 for p in aptas if p["perfil"] == perfil),
                'temas_detectados': dict(temas_por_perfil[perfil]),
                'recomendaciones': recs,
            }
        self.resultados = aptas
        return aptas

    def imprimir_recomendaciones(self):
        if not self.recomendaciones:
            print("\nSin recomendaciones: ningún tema del catálogo apareció "
                  "en la actividad (o todo era tema sensible).")
            return
        print("\n" + "=" * 60)
        print("🎯 RECOMENDACIONES POR PERFIL (ordenadas por evidencia)")
        print("=" * 60)
        for r in self.recomendaciones:
            print(f"\n{r['perfil']}\n  → {r['producto']}  "
                  f"(apoyado por {r['publicaciones_que_apoyan']} publicación/es; "
                  f"temas: {r['temas']})")
            for e in r["evidencias"][:3]:
                print(f"      · [{e['tema']}] {e['extracto'][:110]}...")

    # ---------- Persistencia ----------
    CAMPOS_PUBLICACION = ['perfil', 'urn', 'url_publicacion', 'tipo', 'autor', 'texto',
                          'tiempo', 'fecha_publicacion', 'antiguedad_dias', 'relevancia',
                          'motivos_relevancia', 'hashtags', 'enlaces', 'reacciones',
                          'comentarios', 'fecha_extraccion']

    def guardar_resultados(self):
        """Tres archivos con la misma marca de tiempo, para cruzarlos entre sí."""
        if not self.resultados and not self.recomendaciones:
            print("\nNo hay datos para guardar")
            return {}
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivos = {}
        try:
            nombre = f"{self.prefijo_archivos}_actividad_{marca}.csv"
            with open(nombre, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=self.CAMPOS_PUBLICACION,
                                        extrasaction='ignore')
                writer.writeheader()
                writer.writerows(self.resultados)
            archivos['actividad'] = nombre
            print(f"\n✅ Actividad en: {nombre} ({len(self.resultados)} publicaciones)")
        except Exception as e:
            print(f"❌ Error al guardar la actividad: {e}")

        if self.recomendaciones:
            try:
                nombre = f"{self.prefijo_archivos}_recomendaciones_{marca}.csv"
                with open(nombre, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(
                        f, fieldnames=['perfil', 'producto', 'temas',
                                       'publicaciones_que_apoyan', 'puntuacion',
                                       'razones', 'evidencias', 'urls_publicaciones'],
                        extrasaction='ignore')
                    writer.writeheader()
                    for r in self.recomendaciones:
                        writer.writerow({**r,
                                         'evidencias': " || ".join(e["extracto"] for e in r["evidencias"]),
                                         'urls_publicaciones': ";".join(
                                             e["url_publicacion"] for e in r["evidencias"] if e["url_publicacion"])})
                archivos['recomendaciones'] = nombre
                print(f"✅ Recomendaciones en: {nombre} ({len(self.recomendaciones)} filas)")
            except Exception as e:
                print(f"❌ Error al guardar las recomendaciones: {e}")

        try:
            nombre = f"{self.prefijo_archivos}_resumen_{marca}.json"
            Path(nombre).write_text(json.dumps({
                'generado': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'omitidas_por_tema_sensible': dict(self.omitidas_sensibles),
                'perfiles': self.resumen,
            }, indent=2, ensure_ascii=False), encoding='utf-8')
            archivos['resumen'] = nombre
            print(f"✅ Resumen con evidencia en: {nombre}")
        except Exception as e:
            print(f"❌ Error al guardar el resumen: {e}")
        return archivos

    def guardar_csv(self):
        """Compatibilidad con el nombre anterior: ahora guarda los tres archivos."""
        return self.guardar_resultados()

    def analizar_csv_existente(self, ruta_csv):
        """Genera recomendaciones desde un CSV de actividad ya extraído, sin navegador."""
        with open(ruta_csv, newline='', encoding='utf-8-sig') as f:
            publicaciones = list(csv.DictReader(f))
        print(f"📄 {len(publicaciones)} publicaciones leídas de {ruta_csv}")
        self.analizar_publicaciones(publicaciones)
        self.imprimir_recomendaciones()
        return self.guardar_resultados()

    # ---------- Ejecución ----------
    def ejecutar(self, urls_perfiles, max_posts=10):
        print("=" * 60)
        print("Scraper de actividad de LinkedIn (sesión propia persistente)")
        print("=" * 60)

        if not self.iniciar_navegador():
            print("Se abortó en el inicio de sesión (escribiste 'salir').")
            self.cerrar_navegador()
            return

        try:
            for url in urls_perfiles:
                print(f"\n--- Procesando: {url} ---")
                self.extraer_informacion_perfil(url)   # 1º la ficha, 2º la actividad
                posts = self.extraer_publicaciones_perfil(url, max_posts=max_posts)
                self.resultados.extend(posts)
                # La sesión pudo renovarse navegando: se vuelca al JSON.
                self.guardar_cookies()
                time.sleep(self.gaussian_delay(8, 3))
            # Con toda la actividad junta: temas -> productos recomendados.
            self.analizar_publicaciones(self.resultados)
            self.imprimir_recomendaciones()
        except Exception as e:
            print(f"Error inesperado: {e}")
        finally:
            # Se guarda lo que haya aunque algo haya fallado, y el navegador
            # solo se cierra cuando tú confirmas en cerrar_navegador().
            if self.resultados and not self._analizado:
                self.analizar_publicaciones(self.resultados)
                self.imprimir_recomendaciones()
            self.guardar_resultados()
            self.cerrar_navegador()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Actividad de LinkedIn -> publicaciones -> recomendaciones de producto")
    parser.add_argument("perfiles", nargs="*",
                        help="URLs de perfil (por defecto, la de ejemplo de abajo)")
    parser.add_argument("--max-posts", type=int, default=10,
                        help="publicaciones por perfil (defecto: 10)")
    parser.add_argument("--desde-csv", default="",
                        help="no abre navegador: recomienda desde un CSV de actividad ya extraído")
    parser.add_argument("--cookies", default="linkedin_cookies.json")
    parser.add_argument("--perfil-dir", default="chrome_linkedin_profile")
    args = parser.parse_args()

    scraper = LinkedInActivityScraper(cookie_file=args.cookies,
                                      profile_dir=args.perfil_dir)
    if args.desde_csv:
        scraper.analizar_csv_existente(args.desde_csv)
    else:
        perfiles_objetivo = args.perfiles or [
            "https://www.linkedin.com/in/williamhgates/",
            # Agrega más perfiles aquí
        ]
        scraper.ejecutar(perfiles_objetivo, max_posts=args.max_posts)
