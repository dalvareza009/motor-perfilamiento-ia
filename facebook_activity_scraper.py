# facebook_activity_scraper.py
"""
Extractor de Facebook con TU propia sesión: solo la ficha personal
(estado civil, edad, profesión, empresa, estudios y familia).

Mismo criterio de sesión que el de LinkedIn:
- Chrome con perfil persistente propio (``chrome_facebook_profile/``) más
  ``facebook_cookies.json`` de respaldo. Si Facebook pide login, el navegador
  queda abierto y se espera tu confirmación (consola o front), no se cierra.
- No se leen publicaciones. Solo datos personales declarados en el perfil.

Uso:
    python facebook_activity_scraper.py https://www.facebook.com/usuario
"""
import json
import re
import sys
import time
from datetime import date, datetime
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
from selenium.webdriver.common.keys import Keys

from linkedin_activity_scraper import LinkedInActivityScraper, extraer_red_de, parse_fecha_publicacion
from app.redes_seguidas import tope_publicaciones

MARCAS_MURO_FB = ("/login", "checkpoint", "/recover", "/reg/")
NO_DISPONIBLE = ("este contenido no está disponible", "this content isn't available",
                 "this content isn\u2019t available")
SELECTORES_POST = (
    "[role='article']",
    "[aria-posinset]",
    "div[data-pagelet*='FeedUnit']",
    "div[data-ad-preview='message']",
)


RUIDO_FICHA = {
    "buscar amigos", "nueva notificación en la configuración", "enviar mensaje",
    "seguir", "todo", "información", "amigos", "fotos", "reels", "ver más",
    "datos personales", "editar perfil", "añadir a historia", "añadir foto de portada",
    "añade más amigos para recibir recomendaciones", "crear una publicación",
    "qué estás pensando", "que estas pensando", "vídeo en directo", "foto/vídeo",
    "publicaciones", "filtros", "administrar publicaciones", "vista de lista",
    "vista de cuadrícula", "lo más destacado", "añadir historias destacadas",
    "trabajo y educación", "información básica", "información básica y de contacto",
    "familia y relaciones", "detalles sobre ti", "lugares de residencia",
    "información general", "acerca de", "presentación", "contacto",
    "fecha de nacimiento", "cumpleaños", "estado civil", "profesión",
}
_MESES = {"ene": 1, "enero": 1, "feb": 2, "febrero": 2, "mar": 3, "marzo": 3,
          "abr": 4, "abril": 4, "may": 5, "mayo": 5, "jun": 6, "junio": 6,
          "jul": 7, "julio": 7, "ago": 8, "agosto": 8, "sep": 9, "sept": 9,
          "septiembre": 9, "oct": 10, "octubre": 10, "nov": 11, "noviembre": 11,
          "dic": 12, "diciembre": 12}
_ROL_FAMILIA = re.compile(
    r"^(hermano|hermana|madre|padre|hijo|hija|esposo|esposa|abuelo|abuela|"
    r"nieto|nieta|suegro|suegra|cuñado|cuñada|primo|prima)$", re.I)
_CIVIL = re.compile(
    r"\b(casad[oa]|solter[oa]|divorciad[oa]|viud[oa]|uni[oó]n libre|"
    r"en una relaci[oó]n|comprometid[oa]|separad[oa])\b", re.I)
_FAMILIA = re.compile(
    r"\b(hermano|hermana|madre|padre|hijo|hija|esposo|esposa|abuel[oa]|niet[oa]|"
    r"suegr[oa]|cu[nñ]ad[oa]|familiar|mis padres|mi mam[áa]|mi pap[áa])\b", re.I)
_ESTUDIOS = re.compile(
    r"\b(universidad|liceo|colegio|pregrado|posgrado|estudi[oó]|estudia|egresad[oa]|"
    r"asisti[oó] a)\b", re.I)
_TRABAJO = re.compile(
    r"\b(aut[oó]nomo|independiente|trabaja en|trabaj[oó] en|empleado|docente|profesor|"
    r"profesi[oó]n|cargo)\b", re.I)
_CARGO = re.compile(
    r"\b(analista|gerente|coordinador|coordinadora|asesor|asesora|director|directora|"
    r"jefe|jefa|ingenier[oa]|abogad[oa]|desarrollador|desarrolladora|contador|contadora|"
    r"diseñador|diseñadora|consultor|consultora|administrador|administradora)\b", re.I)
_SECCIONES_ABOUT = ("about", "about_work_and_education", "about_places",
                    "about_contact_and_basic_info", "about_family_and_relationships",
                    "about_details")


def urls_about(profile_url):
    """Páginas de la ficha: trabajo, estudios, edad, estado civil y familia."""
    base = (profile_url or "").rstrip("/")
    if "profile.php" in base.lower():
        sep = "&" if "?" in base else "?"
        return [profile_url] + [f"{base}{sep}sk={s}" for s in _SECCIONES_ABOUT]
    return [profile_url] + [f"{base}/{s}" for s in _SECCIONES_ABOUT]


def urls_likes_y_seguidos(profile_url):
    """Páginas de Me gusta, following y seguidores."""
    from app.redes_seguidas import urls_likes_y_seguidos as _urls
    return _urls(profile_url)


def edad_de_texto(texto, hoy=None):
    """Edad explícita o calculada con una fecha de nacimiento completa."""
    hoy = hoy or date.today()
    t = re.sub(r"\s+", " ", str(texto or ""))
    nacido = re.search(
        r"(?:naci[oó] el|fecha de nacimiento|cumplea[nñ]os)\D{0,30}"
        r"(\d{1,2})\s+de\s+([a-záéí]+)\.?\s+de\s+(\d{4})", t, re.I)
    if nacido:
        mes = _MESES.get(nacido.group(2).lower().strip("."))
        if mes:
            try:
                nacimiento = date(int(nacido.group(3)), mes, int(nacido.group(1)))
            except ValueError:
                nacimiento = None
            if nacimiento:
                edad = hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))
                if 15 <= edad <= 100:
                    return f"{edad} años"
    for frase in re.split(r"[.\n]", t):
        if re.search(r"hij[oa]|niet[oa]|sobrin[oa]", frase, re.I):
            continue
        hallado = re.search(r"\b(\d{1,2})\s+años\b", frase, re.I)
        if not hallado:
            continue
        edad = int(hallado.group(1))
        if 15 <= edad <= 100:
            return f"{edad} años"
    return ""


def _parece_nombre(texto):
    return bool(re.match(
        r"^[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ.'-]{1,40}(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ.'-]{1,40}){0,3}$",
        texto or ""))


def parsear_ficha_facebook(cuerpo, hoy=None):
    """Solo datos personales: edad, estado civil, familia, profesión, empresa y estudios."""
    from app.perfil_redes import quitar_fechas_iso

    info = {"nombre": "", "titular": "", "ubicacion": "", "acerca": "",
            "experiencia": "", "educacion": "", "estado_civil": "", "familia": "",
            "edad": "", "seguidores": ""}
    texto = str(cuerpo or "")
    edad = edad_de_texto(texto, hoy)
    if edad:
        info["edad"] = "Edad declarada en el perfil: " + edad
    m = re.search(r"([\d.,]+\s*(?:mill\.?|mil)?)\s*(?:seguidores|followers|amigos|friends)", texto, re.I)
    if m:
        info["seguidores"] = re.sub(r"\s+", " ", m.group(1)).strip()

    vive, origen, trabajo, estudios, civil, familia = [], [], [], [], [], []

    def clasificar(t):
        t = quitar_fechas_iso(re.sub(r"\s+", " ", t).strip())
        bajo = t.lower().strip(" .")
        if not t or bajo in RUIDO_FICHA or re.match(r"^[\d.,]+\s*(amigos|seguidores)", bajo):
            return
        if re.match(r"^vive en\b", bajo):
            vive.append(t)
        elif re.match(r"^de\b", bajo) and len(t) < 80:
            origen.append(t)
        elif _CIVIL.search(bajo) or bajo.startswith("estado civil"):
            civil.append(t)
        elif _FAMILIA.search(bajo):
            familia.append(t)
        elif _ESTUDIOS.search(bajo) and not _TRABAJO.search(bajo):
            estudios.append(t)
        elif _TRABAJO.search(bajo) or (_CARGO.search(bajo) and re.search(r"\ben\b", bajo)):
            trabajo.append(t)
            if re.search(r"\b(universidad|colegio|liceo)\b", bajo):
                estudios.append(t)

    for linea in texto.splitlines():
        cruda = re.sub(r"\s+", " ", linea).strip()
        if not cruda:
            continue
        if "·" not in cruda:
            clasificar(cruda)
            continue
        piezas = [p.strip() for p in re.split(r"\s*·\s*", cruda) if p.strip()]
        i = 0
        while i < len(piezas):
            if _ROL_FAMILIA.match(piezas[i]) and i + 1 < len(piezas) and _parece_nombre(piezas[i + 1]):
                clasificar(f"{piezas[i]} {piezas[i + 1]}")
                i += 2
            else:
                clasificar(piezas[i])
                i += 1

    if vive or origen:
        info["ubicacion"] = ". ".join(vive + origen)
    if trabajo:
        info["experiencia"] = "Trabajo declarado en el perfil: " + ". ".join(dict.fromkeys(trabajo))
        info["titular"] = trabajo[0]
    if estudios:
        info["educacion"] = "Estudios declarados en el perfil: " + ". ".join(dict.fromkeys(estudios))
    if civil:
        info["estado_civil"] = "Estado civil declarado en el perfil: " + ". ".join(dict.fromkeys(civil))
    if familia:
        info["familia"] = "Familia declarada en el perfil: " + ". ".join(dict.fromkeys(familia))
    presentacion = []
    capturando = False
    for linea in texto.splitlines():
        t = re.sub(r"\s+", " ", linea).strip()
        bajo = t.lower().strip(" .")
        if re.fullmatch(r"(presentación|intro|detalles sobre ti)", bajo):
            capturando = True
            continue
        if capturando:
            if bajo in RUIDO_FICHA or re.match(
                    r"^(trabajo y educación|información básica|familia y relaciones|lugares de residencia)\b", bajo):
                capturando = False
                continue
            if t and len(t) > 12 and not _parece_nombre(t) and "clima" not in bajo:
                presentacion.append(t)
    if presentacion:
        info["bio"] = " ".join(dict.fromkeys(presentacion))[:400]
    info["acerca"] = "\n".join(filter(None, [
        info["titular"], info["ubicacion"], info["experiencia"], info["educacion"],
        info["estado_civil"], info["familia"], info["edad"], info.get("bio")]))
    for clave, valor in list(info.items()):
        if isinstance(valor, str) and valor:
            info[clave] = quitar_fechas_iso(valor)
    from app.perfil_redes import aplicar_lo_publicado
    return aplicar_lo_publicado(info, [{"tipo": "publicacion", "texto": texto}])


def origen_compartida(cabecera, autor=""):
    """Quién publicó el contenido original cuando esta persona lo compartió."""
    if not es_compartida(cabecera):
        return autor
    hallado = re.search(
        r"comparti[oó]\s+(?:una publicación de|un video de|una foto de|from)\s+([^\n.]{2,80})",
        cabecera or "", re.I)
    return (hallado.group(1).strip()[:120] if hallado else autor)


def es_compartida(texto_cabecera):
    t = (texto_cabecera or "").lower()
    return any(f in t for f in ("compartió", "compartio", "ha compartido", "shared",
                                "compartió una", "compartio una"))


class FacebookActivityScraper:
    def __init__(self, cookie_file='facebook_cookies.json',
                 profile_dir='chrome_facebook_profile', confirmar_login=None):
        self.cookie_file = Path(cookie_file)
        self.profile_dir = Path(profile_dir).resolve()
        self.confirmar_login = confirmar_login
        self.driver = None
        self.info = {}
        # El análisis (fechas, relevancia, recomendaciones, archivos) se delega.
        self.analisis = LinkedInActivityScraper(
            cookie_file='linkedin_cookies.json', profile_dir='chrome_facebook_profile')
        self.analisis.prefijo_archivos = "facebook"
        # En Facebook compartir es la forma normal de publicar: la compartida
        # vale LO MISMO que la propia (la ficha sí sigue teniendo prioridad).
        self.analisis.peso_compartida = self.analisis.peso_propia
        self.analisis.priorizar_propias = False

    # ---------- sesión ----------
    def _sanitizar(self, raw):
        if not isinstance(raw, dict) or not raw.get("name") or "value" not in raw:
            return None
        domain = str(raw.get("domain") or ".facebook.com")
        if "facebook.com" not in domain:
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

    def sesion_activa(self):
        url = (self.driver.current_url or "").lower()
        if any(m in url for m in MARCAS_MURO_FB):
            return False
        try:
            nombres = {c["name"] for c in self.driver.get_cookies()}
            if "c_user" not in nombres:
                return False
            if self.driver.find_elements(
                    By.CSS_SELECTOR, "[role='navigation'], [role='banner'], a[href*='/friends']"):
                return True
            # Este Facebook no siempre monta navigation/banner al inicio: el
            # feed con la caja de publicación también prueba la sesión.
            cuerpo = (self.driver.find_element(By.TAG_NAME, "body").text or "").lower()
            return any(m in cuerpo for m in ("qué estás pensando", "que estas pensando",
                                             "crear una publicación", "publicaciones del feed"))
        except Exception:
            return False

    def guardar_cookies(self):
        if self.driver is None:
            return
        try:
            cookies = [c for c in self.driver.get_cookies()
                       if "facebook.com" in (c.get("domain") or "")]
            # No pisar un respaldo con sesión por cookies de una visita sin ella.
            if "c_user" not in {c["name"] for c in cookies} and self.cookie_file.is_file():
                try:
                    previas = json.loads(self.cookie_file.read_text(encoding="utf-8"))
                    if isinstance(previas, dict):
                        previas = previas.get("cookies", [])
                    if any(c.get("name") == "c_user" for c in previas if isinstance(c, dict)):
                        print("⚠ Sin sesión activa: conservo las cookies anteriores.")
                        return
                except Exception:
                    pass
            self.cookie_file.write_text(json.dumps(cookies, indent=2, ensure_ascii=False),
                                        encoding='utf-8')
            print(f"💾 Cookies de Facebook guardadas ({len(cookies)})")
        except Exception as e:
            print(f"⚠ No se pudieron guardar las cookies: {e}")

    def esperar_login_manual(self, contexto=""):
        print("\n🔐 Facebook está pidiendo iniciar sesión. El navegador queda abierto:")
        print("   entra con tu cuenta en esa ventana de Chrome y confirma "
              + ("en la página web." if self.confirmar_login else "aquí con Enter."))
        if not runtime_nube.login_manual_permitido():
            print("En el servidor no hay login manual: hace falta una cookie de sesión vigente.")
            return False
        while True:
            if self.confirmar_login is not None:
                if self.confirmar_login(contexto) != "continuar":
                    return False
            else:
                try:
                    if input("⏎ Enter cuando ya hayas entrado (o 'salir'): ").strip().lower() in ("salir", "q"):
                        return False
                except EOFError:
                    return False
            self.driver.get("https://www.facebook.com/")
            time.sleep(4)
            if self.sesion_activa():
                self.guardar_cookies()
                return True
            print("… Aún no se ve la sesión; termina de entrar y vuelve a confirmar.")

    def iniciar_navegador(self):
        options = Options()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={self.profile_dir}")
        options.add_argument('--window-size=1280,900')
        options.add_argument('--lang=es-ES')
        options.add_argument('--disable-notifications')
        try:
            self.driver = runtime_nube.crear_driver(options)
        except Exception as e:
            print(f"❌ Chrome no arrancó: {e} (¿otro Chrome usa ese perfil?)")
            return False
        self.driver.get("https://www.facebook.com/")
        time.sleep(4)
        if self.sesion_activa():
            print("✅ Sesión de Facebook activa (perfil de Chrome)")
            self.guardar_cookies()
            return True
        if self.cookie_file.is_file():
            try:
                datos = json.loads(self.cookie_file.read_text(encoding='utf-8'))
                if isinstance(datos, dict) and isinstance(datos.get("cookies"), list):
                    datos = datos["cookies"]
                for raw in datos if isinstance(datos, list) else []:
                    cookie = self._sanitizar(raw)
                    if cookie:
                        try:
                            self.driver.add_cookie(cookie)
                        except Exception:
                            continue
                self.driver.get("https://www.facebook.com/")
                time.sleep(4)
                if self.sesion_activa():
                    print("✅ Sesión de Facebook activa (cookies)")
                    self.guardar_cookies()
                    return True
            except Exception as e:
                print(f"⚠ Cookies de Facebook no utilizables: {e}")
        return self.esperar_login_manual("inicio del bot de Facebook")

    def cerrar_navegador(self, preguntar=True):
        if self.driver is None:
            return
        self.guardar_cookies()
        if preguntar:
            try:
                input("\nPulsa Enter para cerrar el navegador… ")
            except EOFError:
                pass
        try:
            self.driver.quit()
        except Exception:
            pass
        self.driver = None

    def _leer_presentacion(self):
        """Texto libre de la tarjeta Presentación / Intro, si la persona escribió algo."""
        try:
            return (self.driver.execute_script("""
                const titulos = [...document.querySelectorAll('h2, h3, span, div')];
                for (const h of titulos) {
                    const t = (h.innerText || '').trim().toLowerCase();
                    if (t !== 'presentación' && t !== 'intro' && t !== 'detalles sobre ti') continue;
                    let n = h.parentElement;
                    for (let i = 0; i < 6 && n; i++, n = n.parentElement) {
                        const txt = (n.innerText || '').trim();
                        if (txt.length > 40 && txt.length < 800) {
                            return txt.split('\\n').filter(l => {
                                const s = l.trim();
                                return s.length > 12 && !/^(presentación|intro|detalles sobre ti)$/i.test(s);
                            }).slice(0, 6).join(' ');
                        }
                    }
                }
                return '';
            """) or "").strip()
        except Exception:
            return ""

    # ---------- perfil y publicaciones ----------
    def extraer_informacion_perfil(self, profile_url):
        print(f"\n👤 Leyendo la ficha personal de Facebook: {profile_url}")
        cuerpos = []
        for url in urls_about(profile_url):
            try:
                self.driver.get(url)
                time.sleep(3)
                cuerpos.append(self.driver.find_element(By.TAG_NAME, "body").text or "")
            except Exception:
                continue
        cuerpo = "\n".join(cuerpos)
        info = {"perfil": profile_url, "nombre": "", "titular": "", "ubicacion": "",
                "acerca": "", "experiencia": "", "educacion": "", "estado_civil": "",
                "familia": "", "edad": "", "seguidores": ""}
        bajo = cuerpo.lower()
        if any(m in bajo for m in NO_DISPONIBLE) and not cuerpos:
            info["acerca"] = "contenido no disponible para esta sesión"
            print("  ⚠ Facebook no muestra este perfil a esta cuenta.")
            self.info = info
            self.analisis.info_perfil[profile_url] = info
            return info
        try:
            texto_h1 = self.driver.find_element(By.TAG_NAME, "h1").text.strip()
            if texto_h1:
                info["nombre"] = texto_h1.splitlines()[0][:120]
        except Exception:
            pass
        if not info["nombre"]:
            titulo = (self.driver.title or "").split("|")[0].strip()
            if titulo and titulo.lower() != "facebook":
                info["nombre"] = titulo[:120]
        parsed = parsear_ficha_facebook(cuerpo)
        for clave in ("titular", "ubicacion", "acerca", "experiencia", "educacion",
                      "estado_civil", "familia", "edad", "seguidores", "bio"):
            if parsed.get(clave) and not info.get(clave):
                info[clave] = parsed[clave]
        bio_dom = self._leer_presentacion()
        if bio_dom:
            info["bio"] = bio_dom[:400]
            if not info.get("titular"):
                info["titular"] = bio_dom.splitlines()[0][:300]
        if not info["nombre"]:
            for patron in (
                r"Añadir foto de portada\n([^\n]+)",
                r"^([A-ZÁÉÍÓÚÑ][^\n]{2,80})\n(?:[\d.,].*(?:seguidores|followers|amigos)|Añadir a historia|Editar perfil|Seguir)",
            ):
                hallado = re.search(patron, cuerpo, re.M)
                if hallado:
                    info["nombre"] = hallado.group(1).strip()[:120]
                    break
        info = extraer_red_de(self.driver, "facebook", profile_url, info)
        self.info = info
        self.analisis.info_perfil[profile_url] = info
        print(f"  OK {info['nombre'] or 'Perfil de Facebook'}"
              + (f" · {info['estado_civil']}" if info.get("estado_civil") else "")
              + (f" · {info['edad']}" if info.get("edad") else ""))
        if info.get("resumen_red"):
            print(f"  · {info['resumen_red']}")
        return info

    def extraer_publicaciones(self, profile_url, max_posts=10):
        max_posts = tope_publicaciones(max_posts)
        visita = profile_url
        if "?" not in visita and not visita.endswith('/'):
            visita += '/'
        print(f"\n📄 Visitando el perfil para bajar a sus publicaciones: {visita}")
        self.driver.get(visita)
        time.sleep(5)
        publicaciones, vistos = [], set()
        for _ronda in range(6):
            articulos, vistos_el = [], set()
            for sel in SELECTORES_POST:
                try:
                    for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                        clave_el = el.id
                        if clave_el in vistos_el:
                            continue
                        vistos_el.add(clave_el)
                        articulos.append(el)
                except Exception:
                    continue
            for art in articulos:
                try:
                    texto = self.analisis._limpiar_texto(art.text, limite=2000)
                    if len(texto) < 40:
                        continue
                    # En el muro, comentarios ajenos salen en el mismo bloque. Si ya
                    # conocemos al dueño, solo se quedan piezas que lo mencionan arriba.
                    dueno = (self.info.get("nombre") or "").strip().lower()
                    if dueno:
                        cabecera_corta = "\n".join(texto.splitlines()[:3]).lower()
                        if dueno not in cabecera_corta:
                            continue
                    clave = re.sub(r"\s+", " ", texto.lower())[:200]
                    if clave in vistos:
                        continue
                    vistos.add(clave)
                    cabecera = texto[:350]
                    tiempo = ""
                    for linea in texto.splitlines()[:12]:
                        if parse_fecha_publicacion(linea) or re.match(
                                r"^\d+\s*(h|d|sem|mes|año)s?\.?$", linea.strip(), re.I):
                            tiempo = linea.strip()
                            break
                    autor = ""
                    try:
                        autor = art.find_element(By.CSS_SELECTOR, "strong, h2, h3").text.strip().splitlines()[0][:120]
                    except Exception:
                        pass
                    compartida = es_compartida(cabecera)
                    if compartida:
                        autor = origen_compartida(cabecera, autor)
                    publicaciones.append({
                        'perfil': profile_url, 'urn': 'N/A', 'url_publicacion': '',
                        'tipo': 'compartida' if compartida else 'publicacion',
                        'autor': autor, 'texto': texto, 'tiempo': tiempo,
                        'hashtags': ";".join(self.analisis.extraer_hashtags(texto)),
                        'enlaces': '', 'reacciones': '', 'comentarios': '',
                        'fecha_extraccion': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    print(f"  📝 [{len(publicaciones)}] {texto[:60]}...")
                    if len(publicaciones) >= max_posts * 2:  # margen: luego filtra el año
                        break
                except Exception:
                    continue
            if len(publicaciones) >= max_posts * 2:
                break
            self.driver.execute_script("window.scrollBy(0, 1100);")
            time.sleep(2.5)
        vigentes = self.analisis.filtrar_y_ordenar(publicaciones)
        from app.redes_seguidas import aplicar_a_info
        self.info = aplicar_a_info(self.info, posts=vigentes)
        self.analisis.info_perfil[profile_url] = self.info
        print(f"  ✔ {len(vigentes)} dentro del último año "
              f"({self.analisis.ultimas_descartadas} antiguas descartadas)")
        return vigentes[:max_posts]

    # ---------- página: likes, comentarios y contacto ----------
    def extraer_ficha_corta(self, profile_url):
        """Nombre, trabajo, ciudad y contacto público, sin listas de seguidos."""
        from app.facebook_pagina import formatear_contacto
        from app.perfil_redes import contactos_de_texto

        cuerpos = []
        for url in urls_about(profile_url)[:4]:
            try:
                self.driver.get(url)
                time.sleep(2.2)
                cuerpos.append(self.driver.find_element(By.TAG_NAME, "body").text or "")
            except Exception:
                continue
        cuerpo = "\n".join(cuerpos)
        info = {"nombre": "", "titular": "", "ubicacion": "", "acerca": "",
                "experiencia": "", "educacion": "", "contacto": "", "contactos": []}
        bajo = cuerpo.lower()
        if any(m in bajo for m in NO_DISPONIBLE) and not cuerpos:
            info["acerca"] = "contenido no disponible para esta sesión"
            return info
        try:
            texto_h1 = self.driver.find_element(By.TAG_NAME, "h1").text.strip()
            if texto_h1:
                info["nombre"] = texto_h1.splitlines()[0][:120]
        except Exception:
            pass
        parsed = parsear_ficha_facebook(cuerpo)
        for clave in ("nombre", "titular", "ubicacion", "acerca", "experiencia", "educacion", "edad"):
            if parsed.get(clave) and not info.get(clave):
                info[clave] = parsed[clave]
        info["contactos"] = contactos_de_texto(cuerpo)
        info["contacto"] = formatear_contacto(info, profile_url)
        return info

    def _nombre_pagina(self):
        try:
            h1 = self.driver.find_element(By.TAG_NAME, "h1").text.strip()
            if h1:
                return h1.splitlines()[0][:120]
        except Exception:
            pass
        titulo = (self.driver.title or "").split("|")[0].strip()
        if titulo and titulo.lower() != "facebook":
            return titulo[:120]
        return ""

    def _urls_publicaciones_pagina(self, max_posts):
        vistos, orden = set(), []
        for _ronda in range(8):
            halladas = self.driver.execute_script("""
                const arts = [...document.querySelectorAll("[role='article'], [aria-posinset]")];
                return arts.map(art => {
                  const a = art.querySelector(
                    'a[href*="/posts/"], a[href*="permalink.php"], a[href*="story_fbid"], a[href*="/photos/"]');
                  const lineas = (art.innerText || '').split('\\n')
                    .map(l => l.trim()).filter(l => l.length > 18);
                  return {url: a ? a.href : '', texto: lineas.slice(0, 5).join(' ').slice(0, 400)};
                });
            """) or []
            for item in halladas:
                url = (item.get("url") or "").split("?")[0].strip()
                if not url or url in vistos:
                    continue
                vistos.add(url)
                orden.append({"url": url, "texto": item.get("texto") or ""})
            if len(orden) >= max_posts:
                break
            self.driver.execute_script("window.scrollBy(0, 1400);")
            time.sleep(2.2)
        return orden[:max_posts]

    def _expandir_comentarios(self):
        for _ in range(8):
            clic = self.driver.execute_script("""
                const claves = ['ver más comentarios', 'ver mas comentarios', 'view more comments',
                                'comentarios anteriores', 'previous comments',
                                'ver todos los comentarios', 'view all comments'];
                const els = [...document.querySelectorAll('div[role="button"], span, a')];
                for (const el of els) {
                  const t = (el.innerText || '').trim().toLowerCase();
                  if (!t || t.length > 60) continue;
                  if (claves.some(c => t === c || t.startsWith(c))) { el.click(); return t; }
                }
                return '';
            """)
            if not clic:
                break
            time.sleep(1.3)

    def _entradas_visibles(self, pagina_url, solo=""):
        raw = self.driver.execute_script("""
            const out = [];
            const nodos = [...document.querySelectorAll('[aria-label]')];
            for (const n of nodos) {
              const lab = n.getAttribute('aria-label') || '';
              const m = lab.match(/^(?:Comentario de|Comment by)\\s+(.+)$/i);
              if (!m) continue;
              const a = n.querySelector('a[href]');
              let texto = '';
              for (const d of n.querySelectorAll('[dir="auto"]')) {
                const t = (d.innerText || '').trim();
                if (t && t !== m[1] && t.length > 1 && t.length < 500
                    && !/^(me gusta|like|responder|reply|hace \\d)/i.test(t)) {
                  texto = t; break;
                }
              }
              out.push({href: a ? a.href : '', nombre: m[1], tipo: 'comentario', texto});
            }
            const dialogo = document.querySelector('[role="dialog"]');
            if (dialogo) {
              for (const a of dialogo.querySelectorAll('a[href]')) {
                const nombre = (a.innerText || a.getAttribute('aria-label') || '')
                  .trim().split('\\n')[0];
                if (nombre && a.href) out.push({href: a.href, nombre, tipo: 'like', texto: ''});
              }
            }
            return out;
        """) or []
        entradas = []
        for item in raw:
            tipo = item.get("tipo") or "comentario"
            if solo and tipo != solo:
                continue
            entradas.append({
                "href": item.get("href"),
                "nombre": item.get("nombre"),
                "tipo": tipo,
                "texto": item.get("texto") or "",
                "pagina": pagina_url,
            })
        return entradas

    def _cerrar_dialogo(self):
        try:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.4)
        except Exception:
            pass

    def _entradas_dialogo(self, pagina_url, tipo):
        raw = self.driver.execute_script("""
            const tipo = arguments[0];
            const d = document.querySelector('[role="dialog"]');
            if (!d) return [];
            const out = [];
            for (const a of d.querySelectorAll('a[href]')) {
              const nombre = (a.innerText || a.getAttribute('aria-label') || '')
                .trim().split('\\n')[0];
              if (nombre && a.href) out.push({href: a.href, nombre, tipo, texto: ''});
            }
            return out;
        """, tipo) or []
        return [{
            "href": item.get("href"),
            "nombre": item.get("nombre"),
            "tipo": tipo,
            "texto": "",
            "pagina": pagina_url,
        } for item in raw]

    def _dialogo_de_post(self, pagina_url, tipo):
        """Abre el listado de me gusta o de shares y saca los perfiles."""
        if tipo == "compartido":
            primero = r"quién compartió|quien compartio|see who shared|ver quiénes compartieron|ver quienes compartieron"
            segundo = r"compartidos|shares|veces compart|shared this"
        else:
            primero = r"ver quién reaccionó|ver quien reacciono|see who reacted|todas las reacciones|all reactions"
            segundo = r"me gusta|like|reaccion"
            tipo = "like"
        try:
            clic = self.driver.execute_script("""
                const primero = new RegExp(arguments[0], 'i');
                const segundo = new RegExp(arguments[1], 'i');
                const labs = [...document.querySelectorAll('[aria-label], [role="button"]')];
                for (const el of labs) {
                  const t = (el.getAttribute('aria-label') || el.innerText || '');
                  if (primero.test(t) && t.length < 90) { el.click(); return t; }
                }
                for (const el of labs) {
                  const t = (el.getAttribute('aria-label') || '');
                  if (t.length < 90 && /\\d/.test(t) && segundo.test(t)) { el.click(); return t; }
                }
                return '';
            """, primero, segundo)
            if not clic:
                return []
            time.sleep(2)
            for _ in range(5):
                self.driver.execute_script("""
                    const d = document.querySelector('[role="dialog"]');
                    if (!d) return;
                    const sc = [...d.querySelectorAll('*')].find(n => n.scrollHeight > n.clientHeight + 40) || d;
                    sc.scrollTop = sc.scrollHeight;
                """)
                time.sleep(0.8)
            entradas = self._entradas_dialogo(pagina_url, tipo)
            self._cerrar_dialogo()
            return entradas
        except Exception as e:
            print(f"  ⚠ No se leyó el listado ({tipo}): {e}")
            self._cerrar_dialogo()
            return []

    def extraer_interactuantes_pagina(self, page_url, max_posts=5, max_personas=30, tarea=None):
        """Likes y comentarios de las publicaciones de una página, con ficha de contacto."""
        from app.facebook_pagina import (TOPE_PERSONAS, acercamiento, clasificar_url_pagina,
                                         formatear_contacto, fusionar, persistir,
                                         url_perfil_facebook)

        page_url = clasificar_url_pagina(page_url)
        if not page_url:
            return {"ok": False, "motivo": "Indica la URL de una página de Facebook."}
        max_posts = max(1, min(int(max_posts or 5), 10))
        max_personas = max(1, min(int(max_personas or 30), TOPE_PERSONAS))
        print(f"\n📄 Página de Facebook: {page_url}")
        self.driver.get(page_url)
        time.sleep(4)
        nombre_pagina = self._nombre_pagina() or page_url.rsplit("/", 1)[-1]
        print(f"  {nombre_pagina}")
        posts = self._urls_publicaciones_pagina(max_posts)
        if not posts:
            print("  ⚠ No se vieron publicaciones. ¿La sesión puede ver la página?")
        personas, vistos_evento = [], set()
        if tarea:
            tarea.avance(0, max(len(posts), 1) + max_personas)

        def mezclar(extra, publicacion=""):
            pub = publicacion or ""
            for item in extra:
                perfil = url_perfil_facebook(item.get("href") or item.get("perfil") or "", page_url)
                clave = (perfil, item.get("tipo"), pub[:80], (item.get("texto") or "")[:80])
                if not perfil or clave in vistos_evento:
                    continue
                vistos_evento.add(clave)
                fusionar(personas, {
                    **item,
                    "pagina": page_url,
                    "publicacion": pub,
                })

        for i, post in enumerate(posts, 1):
            if tarea and getattr(tarea, "cancelada", False):
                print("Detenida.")
                break
            print(f"  Publicación {i}/{len(posts)}: {(post.get('texto') or '')[:70]}")
            try:
                self.driver.get(post["url"])
                time.sleep(3)
            except Exception as e:
                print(f"  ⚠ No se abrió la publicación: {e}")
                continue
            self._expandir_comentarios()
            mezclar(self._entradas_visibles(page_url, solo="comentario"), post.get("texto") or "")
            mezclar(self._dialogo_de_post(page_url, "like"), post.get("texto") or "")
            mezclar(self._dialogo_de_post(page_url, "compartido"), post.get("texto") or "")
            if tarea:
                tarea.avance(i, len(posts) + max_personas)

        personas.sort(key=lambda p: (p["comentarios"], p.get("compartidos") or 0, p["likes"]), reverse=True)
        print(f"  {len(personas)} persona(s) distintas. Ficha de las primeras {min(len(personas), max_personas)}.")
        for i, p in enumerate(personas):
            if tarea and getattr(tarea, "cancelada", False):
                break
            if i < max_personas:
                print(f"  Ficha {i + 1}/{min(len(personas), max_personas)}: {p.get('nombre') or p['perfil']}")
                try:
                    info = self.extraer_ficha_corta(p["perfil"])
                except Exception as e:
                    print(f"  ⚠ No se leyó la ficha: {e}")
                    info = {}
                if info.get("nombre"):
                    p["nombre"] = info["nombre"]
                p["ficha"] = info.get("acerca") or info.get("titular") or p.get("ficha") or ""
                p["ubicacion"] = info.get("ubicacion") or ""
                p["contacto"] = info.get("contacto") or formatear_contacto(info, p["perfil"])
                if tarea:
                    tarea.avance(len(posts) + i + 1, len(posts) + max_personas)
            if not p.get("contacto"):
                p["contacto"] = formatear_contacto({}, p["perfil"])
            p["acercamiento"] = acercamiento(p, nombre_pagina)

        n = persistir(page_url, nombre_pagina, personas)
        print(f"  Guardadas {n} persona(s) que interactuaron con {nombre_pagina}.")
        return {
            "ok": True,
            "pagina": page_url,
            "pagina_nombre": nombre_pagina,
            "publicaciones": len(posts),
            "personas": personas,
            "guardados": n,
        }

    # ---------- ejecución ----------
    def ejecutar(self, profile_url, max_posts=10):
        if not self.iniciar_navegador():
            self.cerrar_navegador(preguntar=False)
            return {"ok": False, "motivo": "No se confirmó el inicio de sesión en Facebook."}
        try:
            info = self.extraer_informacion_perfil(profile_url)
            return {"ok": True, "perfil": profile_url, "perfil_info": info,
                    "solo_perfil": True, "publicaciones": 0,
                    "descartadas_antiguas": 0, "omitidas_sensibles": 0,
                    "recomendaciones": []}
        finally:
            self.cerrar_navegador(preguntar=False)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Facebook: solo la ficha personal del perfil")
    parser.add_argument("url", help="https://www.facebook.com/usuario")
    parser.add_argument("--max-posts", type=int, default=10)
    args = parser.parse_args()
    bot = FacebookActivityScraper()
    try:
        resultado = bot.ejecutar(args.url, max_posts=args.max_posts)
        print(resultado.get("motivo", "Listo."))
    except Exception as e:
        bot.cerrar_navegador(preguntar=False)
        raise SystemExit(f"Error: {e}") from None
