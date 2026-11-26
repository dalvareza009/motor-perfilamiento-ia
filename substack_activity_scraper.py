# substack_activity_scraper.py
"""
Extractor de Substack con tu sesión: ficha (nombre, bio, newsletter),
notas y posts. El texto va a hechos, contenido e intereses.

Chrome con ``chrome_substack_profile/`` y ``substack_cookies.json``.
Los perfiles públicos se leen sin login; si Substack pide entrar, el
navegador queda abierto hasta que confirmes.

Uso:
    python substack_activity_scraper.py https://substack.com/@usuario
    python substack_activity_scraper.py https://usuario.substack.com/
"""
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app import runtime_nube
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from linkedin_activity_scraper import (LinkedInActivityScraper, expandir_ver_mas, extraer_red_de,
                                       parse_fecha_publicacion)
from app.redes_seguidas import elegir_publicaciones, tope_publicaciones

MARCAS_MURO = ("/sign-in", "/signin", "/login", "accounts.substack.com")
SUBSTACK_RESERVADOS = {
    "www", "api", "cdn", "open", "app", "support", "help", "onboarding",
    "login", "signin", "signup", "account", "accounts", "static", "media",
    "home", "inbox", "notes", "explore", "publish", "settings", "chat",
}
RUIDO_FICHA = {
    "subscribe", "suscribirse", "message", "mensaje", "share", "compartir",
    "activity", "actividad", "replies", "likes", "restacks", "notes", "notas",
    "home", "inicio", "explore", "explorar", "profile", "perfil", "create",
    "crear", "sign in", "iniciar sesión", "log in", "get app", "see subscribers",
    "recommendations", "subscriptions", "publicación", "publication",
}
_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio",
          "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def es_no_disponible(texto):
    t = (texto or "").lower()
    return ("page not found" in t or "página no encontrada" in t
            or "this page doesn't exist" in t or "couldn't find" in t)


def handle_de_substack(url):
    u = str(url or "").strip()
    partes = urlparse(u)
    host = (partes.hostname or "").lower().removeprefix("www.")
    path = [s for s in (partes.path or "").split("/") if s]
    if host == "substack.com" and path and path[0].startswith("@"):
        return path[0][1:].lower()
    if host.endswith(".substack.com"):
        sub = host[: -len(".substack.com")]
        if sub and "." not in sub and sub not in SUBSTACK_RESERVADOS:
            return sub.lower()
    return ""


def url_perfil_substack(url):
    from app.perfil_redes import clasificar_url
    c = clasificar_url(url)
    return c[1] if c and c[0] == "substack" else (url or "").split("?")[0].rstrip("/") + "/"


def url_de_publicacion(href, pub_url=""):
    m = re.search(r"(https?://[^/\s]+)/p/([^/?#]+)", href or "", re.I)
    if m:
        return f"{m.group(1).rstrip('/')}/p/{m.group(2)}"
    slug = (href or "").strip().strip("/")
    if pub_url and slug and "/" not in slug and " " not in slug:
        return f"{pub_url.rstrip('/')}/p/{slug}"
    return ""


def tiempo_legible(etiqueta, datetime_attr=""):
    etiqueta = re.sub(r"\s+", " ", (etiqueta or "")).strip()
    es_iso = bool(re.match(r"\d{4}-\d{2}-\d{2}", etiqueta))
    if etiqueta and not es_iso and parse_fecha_publicacion(etiqueta):
        return etiqueta
    fecha = parse_fecha_publicacion(datetime_attr) or (parse_fecha_publicacion(etiqueta) if es_iso else None)
    if fecha:
        return f"{fecha.day} de {_MESES[fecha.month - 1]} de {fecha.year}"
    return "" if es_iso else etiqueta


def _texto_links(links):
    if isinstance(links, dict):
        return " ".join(str(v) for v in links.values() if v)
    if isinstance(links, list):
        partes = []
        for item in links:
            if isinstance(item, str):
                partes.append(item)
            elif isinstance(item, dict):
                partes.append(str(item.get("url") or item.get("href") or ""))
        return " ".join(partes)
    return str(links or "")


def parsear_ficha_substack(cuerpo, nombre_conocido="", perfil=""):
    """Nombre, bio, newsletter y otras redes. Sin botones ni recuentos."""
    from app.perfil_redes import anexar_otras_redes, aplicar_lo_publicado, quitar_fechas_iso

    info = {"nombre": (nombre_conocido or "").strip(), "titular": "", "ubicacion": "",
            "acerca": "", "experiencia": "", "educacion": "", "estado_civil": "",
            "familia": "", "bio": "", "handle": handle_de_substack(perfil),
            "perfil": perfil, "privado": False, "no_disponible": False}
    texto = str(cuerpo or "")
    info["no_disponible"] = es_no_disponible(texto)
    trabajo, resto = [], []
    for linea in texto.splitlines():
        t = quitar_fechas_iso(re.sub(r"\s+", " ", linea).strip())
        bajo = t.lower().strip(" .•·@")
        if not t or bajo in RUIDO_FICHA or len(t) > 500:
            continue
        if t.startswith("@") and len(t) < 40 and not info.get("handle"):
            info["handle"] = t[1:].lower()
            continue
        if t.lower().startswith("http") or any(d in bajo for d in (
                "instagram.com", "facebook.com", "x.com/", "twitter.com", "linkedin.com")):
            info = anexar_otras_redes(info, t, "substack", perfil)
            continue
        if re.search(r"\b(newsletter|substack|escribo|writer|periodista|"
                     r"analista|emprendedor|founder|editor)\b", bajo, re.I):
            trabajo.append(t)
        elif re.match(r"^vive en\b|^en [A-ZÁÉÍÓÚÑ]", t) and len(t) < 80:
            info["ubicacion"] = t
        elif not info["nombre"] and re.match(
                r"^[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ.'-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ.'-]+){0,5}$", t
                ) and len(t) < 80 and t.lower() not in RUIDO_FICHA:
            info["nombre"] = t[:120]
        elif len(t) > 2:
            resto.append(t)
    if trabajo:
        info["experiencia"] = "Publicación en Substack: " + ". ".join(trabajo[:3])
        info["titular"] = trabajo[0][:300]
    if not info["titular"] and resto:
        info["titular"] = resto[0][:300]
    utiles = [p for p in resto if p not in (info["titular"], info["nombre"])][:8]
    if utiles:
        info["bio"] = "\n".join(utiles)[:400]
    info["acerca"] = "\n".join(filter(None, [
        info["titular"], info["ubicacion"], info["experiencia"], info.get("bio")]))
    for clave, valor in list(info.items()):
        if isinstance(valor, str) and valor:
            info[clave] = quitar_fechas_iso(valor)
    info = anexar_otras_redes(info, texto, "substack", perfil)
    return aplicar_lo_publicado(info, [{"tipo": "publicacion", "texto": info.get("acerca") or ""}],
                               origen="ficha")


def ficha_desde_api(data, perfil=""):
    """Ficha a partir del JSON público de Substack (perfil o publicación)."""
    from app.perfil_redes import anexar_otras_redes

    data = data or {}
    user = data.get("user") if isinstance(data.get("user"), dict) else data
    pub = data.get("publication") if isinstance(data.get("publication"), dict) else {}
    if not pub:
        for item in data.get("publicationUsers") or data.get("publications") or []:
            cand = item.get("publication") if isinstance(item, dict) else None
            if isinstance(cand, dict) and cand.get("name"):
                pub = cand
                break
            if isinstance(item, dict) and (item.get("subdomain") or item.get("name")):
                pub = item
                break
    nombre = (user.get("name") or pub.get("author_name") or "")
    handle = (user.get("handle") or data.get("subdomain") or handle_de_substack(perfil))
    bio = (user.get("bio") or data.get("bio") or pub.get("hero_text")
           or data.get("hero_text") or "")
    newsletter = pub.get("name") or ""
    if newsletter and nombre and newsletter.strip() == str(nombre).strip():
        newsletter = ""
    lineas = [nombre, f"@{handle}" if handle else "", newsletter, bio]
    twitter = user.get("twitter_screen_name") or data.get("twitter_screen_name") or ""
    if twitter:
        lineas.append(f"https://x.com/{str(twitter).lstrip('@')}")
    lineas.append(_texto_links(user.get("links") or data.get("links") or pub.get("links")))
    info = parsear_ficha_substack("\n".join(p for p in lineas if p), nombre, perfil)
    if newsletter:
        info["experiencia"] = f"Publicación en Substack: {newsletter}."
        if not info.get("titular"):
            info["titular"] = newsletter[:300]
    if handle:
        info["handle"] = str(handle).lstrip("@").lower()
    pubs = []
    for item in data.get("publicationUsers") or data.get("publications") or []:
        p = item.get("publication") if isinstance(item, dict) else None
        p = p if isinstance(p, dict) else (item if isinstance(item, dict) else {})
        sub = (p.get("subdomain") or "").strip()
        if sub:
            pubs.append(f"https://{sub}.substack.com/")
        custom = (p.get("custom_domain") or "").strip()
        if custom and not custom.startswith("http"):
            pubs.append(f"https://{custom}/")
    if pubs:
        info["newsletters"] = pubs
    sid = user.get("id") or data.get("id") or pub.get("author_id")
    if sid:
        info["substack_id"] = sid
    info = anexar_otras_redes(info, "\n".join(pubs + lineas), "substack", perfil)
    return info


def posts_desde_archivo(items, perfil, nombre="", max_posts=10):
    """Convierte el archivo JSON de Substack en publicaciones del motor."""
    max_posts = tope_publicaciones(max_posts)
    salida = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        titulo = re.sub(r"\s+", " ", str(item.get("title") or "")).strip()
        sub = re.sub(r"\s+", " ", str(item.get("subtitle") or "")).strip()
        cuerpo = re.sub(r"\s+", " ", str(
            item.get("truncated_body_text") or item.get("description") or "")).strip()
        href = (item.get("canonical_url") or item.get("canonicalUrl")
                or url_de_publicacion(item.get("slug") or "", perfil))
        if not titulo and not cuerpo:
            continue
        partes = [p for p in (titulo, sub, cuerpo) if p]
        texto = "\n".join(partes)
        audience = str(item.get("audience") or "").lower()
        if audience in ("only_paid", "founding") and "vista previa" not in texto.lower():
            texto = (texto + "\n(Vista previa: el resto es de pago.)").strip()
        fecha = item.get("post_date") or item.get("postDate") or ""
        bylines = item.get("publishedBylines") or []
        autor = nombre
        if isinstance(bylines, list) and bylines and isinstance(bylines[0], dict):
            autor = bylines[0].get("name") or autor
        salida.append({
            "perfil": perfil, "urn": str(item.get("id") or "N/A"),
            "url_publicacion": href, "tipo": "publicacion", "autor": autor or nombre,
            "texto": texto[:2000], "tiempo": tiempo_legible("", str(fecha)),
            "hashtags": "", "enlaces": href, "reacciones": "", "comentarios": "",
            "alts": [], "imagenes": [], "n_imagenes": 0, "tiene_imagenes": False,
            "fecha_extraccion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        if len(salida) >= max_posts * 3:
            break
    return salida


def _texto_nota(body):
    if isinstance(body, str):
        t = re.sub(r"<[^>]+>", " ", body)
        return re.sub(r"\s+", " ", t).strip()
    if isinstance(body, dict):
        if body.get("text"):
            return str(body.get("text") or "").strip()
        return " ".join(filter(None, (_texto_nota(body.get("content")),
                                       _texto_nota(body.get("children")))))
    if isinstance(body, list):
        return " ".join(p for p in (_texto_nota(x) for x in body) if p)
    return ""


def _autor_de(item):
    if isinstance(item, dict):
        if item.get("name"):
            return str(item["name"]).strip()
        by = item.get("publishedBylines") or item.get("bylines") or []
        if isinstance(by, list) and by and isinstance(by[0], dict):
            return str(by[0].get("name") or "").strip()
    return ""


def posts_desde_notas(items, perfil, nombre="", max_posts=10):
    """Notas propias y restacks (lo que la persona republica)."""
    max_posts = tope_publicaciones(max_posts)
    salida = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        restack = item.get("restacked_post") or item.get("restackedPost")
        if not restack and (
                item.get("isRestack") or str(item.get("type") or "").lower() in ("restack", "share")):
            cand = item.get("post") or item.get("restack")
            restack = cand if isinstance(cand, dict) else None
        if not isinstance(restack, dict):
            restack = None
        cuerpo = _texto_nota(item.get("body") or item.get("comment") or item.get("text") or "")
        href = (item.get("canonical_url") or item.get("url") or "")
        fotos = item.get("photos") or item.get("images") or []
        alts = []
        for f in fotos if isinstance(fotos, list) else []:
            if isinstance(f, dict) and (f.get("alt") or f.get("caption")):
                alts.append(str(f.get("alt") or f.get("caption")))
            elif isinstance(f, str):
                alts.append("")
        if restack:
            titulo = re.sub(r"\s+", " ", str(restack.get("title") or "")).strip()
            sub = re.sub(r"\s+", " ", str(restack.get("subtitle") or "")).strip()
            preview = re.sub(r"\s+", " ", str(
                restack.get("truncated_body_text") or restack.get("description") or "")).strip()
            href = (restack.get("canonical_url") or restack.get("canonicalUrl") or href)
            autor = _autor_de(restack) or _autor_de(item)
            texto = "\n".join(p for p in (cuerpo, titulo, sub, preview) if p)
            tipo = "compartida"
        else:
            autor = nombre
            texto = cuerpo
            tipo = "publicacion"
            href = href or (item.get("canonical_url") or "")
        if not texto and not alts:
            continue
        fecha = item.get("date") or item.get("post_date") or item.get("createdAt") or ""
        salida.append({
            "perfil": perfil, "urn": str(item.get("id") or "N/A"),
            "url_publicacion": href, "tipo": tipo, "autor": autor or nombre,
            "texto": (texto or "Restack")[:2000],
            "tiempo": tiempo_legible("", str(fecha)),
            "hashtags": "", "enlaces": href, "reacciones": "", "comentarios": "",
            "alts": [a for a in alts if a], "imagenes": [],
            "n_imagenes": len(fotos) if isinstance(fotos, list) else 0,
            "tiene_imagenes": bool(fotos),
            "fecha_extraccion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        if len(salida) >= max_posts * 3:
            break
    return salida


class SubstackActivityScraper:
    def __init__(self, cookie_file="substack_cookies.json",
                 profile_dir="chrome_substack_profile", confirmar_login=None):
        self.cookie_file = Path(cookie_file)
        self.profile_dir = Path(profile_dir).resolve()
        self.confirmar_login = confirmar_login
        self.driver = None
        self.info = {}
        self.analisis = LinkedInActivityScraper(
            cookie_file="linkedin_cookies.json", profile_dir="chrome_substack_profile")
        self.analisis.prefijo_archivos = "substack"
        self.analisis.peso_compartida = self.analisis.peso_propia
        self.analisis.priorizar_propias = False

    def _sanitizar(self, raw):
        if not isinstance(raw, dict) or not raw.get("name") or "value" not in raw:
            return None
        domain = str(raw.get("domain") or ".substack.com")
        if "substack.com" not in domain:
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
        return any(m in url for m in MARCAS_MURO)

    def sesion_activa(self):
        if self.driver is None or self._en_muro_de_login():
            return False
        try:
            nombres = {c["name"] for c in self.driver.get_cookies()}
        except Exception:
            return False
        if "substack.sid" in nombres:
            return True
        return True

    def guardar_cookies(self):
        if self.driver is None:
            return
        try:
            cookies = [c for c in self.driver.get_cookies()
                       if "substack.com" in (c.get("domain") or "")]
            if "substack.sid" not in {c["name"] for c in cookies} and self.cookie_file.is_file():
                try:
                    previas = json.loads(self.cookie_file.read_text(encoding="utf-8"))
                    if isinstance(previas, dict):
                        previas = previas.get("cookies", [])
                    if any(c.get("name") == "substack.sid" for c in previas if isinstance(c, dict)):
                        print("Sin sesion activa: conservo las cookies anteriores.")
                        return
                except Exception:
                    pass
            self.cookie_file.write_text(json.dumps(cookies, indent=2, ensure_ascii=False),
                                        encoding="utf-8")
            print(f"Cookies de Substack guardadas ({len(cookies)})")
        except Exception as e:
            print(f"No se pudieron guardar las cookies: {e}")

    def _cerrar_avisos(self):
        try:
            self.driver.execute_script("""
                const textos = ['accept', 'aceptar', 'got it', 'continue', 'continuar',
                                'allow all cookies', 'permitir todas las cookies', 'aceptar todo'];
                for (const b of document.querySelectorAll('button, [role="button"]')) {
                    const t = (b.innerText || '').trim().toLowerCase();
                    if (textos.includes(t)) b.click();
                }
            """)
        except Exception:
            pass

    def esperar_login_manual(self, contexto=""):
        print("\nSubstack esta pidiendo iniciar sesion. El navegador queda abierto:")
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
            self.driver.get("https://substack.com/")
            time.sleep(3)
            self._cerrar_avisos()
            if self.sesion_activa() and not self._en_muro_de_login():
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
        self.driver.get("https://substack.com/")
        time.sleep(3)
        self._cerrar_avisos()
        if not self._en_muro_de_login():
            print("Substack abierto (perfil público; login solo si lo pide).")
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
                self.driver.get("https://substack.com/")
                time.sleep(3)
                self._cerrar_avisos()
                if not self._en_muro_de_login():
                    print("Sesion de Substack activa (cookies)")
                    self.guardar_cookies()
                    return True
            except Exception as e:
                print(f"Cookies de Substack no utilizables: {e}")
        return self.esperar_login_manual("inicio del bot de Substack")

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

    def _fetch_json(self, url):
        try:
            self.driver.set_script_timeout(18)
            data = self.driver.execute_async_script("""
                const url = arguments[0];
                const done = arguments[arguments.length - 1];
                fetch(url, {credentials: 'include'})
                  .then(r => r.ok ? r.json() : Promise.reject('HTTP ' + r.status))
                  .then(j => done(j))
                  .catch(e => done({__error: String(e)}));
            """, url)
            if isinstance(data, dict) and data.get("__error"):
                return None
            return data
        except Exception as e:
            print(f"  API Substack no respondió: {e}")
            return None

    def extraer_informacion_perfil(self, profile_url):
        print(f"\nLeyendo primero la ficha de Substack: {profile_url}")
        url = url_perfil_substack(profile_url)
        self.driver.get(url)
        time.sleep(3)
        self._cerrar_avisos()
        if self._en_muro_de_login():
            if not self.esperar_login_manual(url):
                return {}
            self.driver.get(url)
            time.sleep(3)
        handle = handle_de_substack(url)
        data = None
        if handle and "substack.com/@" in url.replace("www.", ""):
            data = self._fetch_json(f"https://substack.com/api/v1/user/{handle}/public_profile")
        if data is None:
            data = self._fetch_json(url.rstrip("/") + "/api/v1/publication")
        info = ficha_desde_api(data, url) if data else {}
        if not info.get("nombre"):
            try:
                cuerpo = self.driver.find_element(By.TAG_NAME, "body").text or ""
            except Exception:
                cuerpo = ""
            info = parsear_ficha_substack(cuerpo[:3500], info.get("nombre") or "", url)
        info["perfil"] = url
        info["handle"] = info.get("handle") or handle
        if info.get("no_disponible"):
            print("  Substack no muestra este perfil.")
        else:
            print(f"  OK {info.get('nombre') or handle or 'Perfil de Substack'}")
        if not info.get("no_disponible"):
            info = extraer_red_de(self.driver, "substack", url, info)
        self.info = info
        self.analisis.info_perfil[url] = info
        return info

    def _archivo_de(self, pub_url, limite=20):
        base = (pub_url or "").rstrip("/")
        if not base:
            return []
        if "substack.com/@" in base.replace("www.", ""):
            return []
        self.driver.get(base + "/")
        time.sleep(2)
        self._cerrar_avisos()
        data = self._fetch_json(f"{base}/api/v1/archive?sort=new&search=&offset=0&limit={int(limite)}")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("posts") or data.get("items") or []
        return []

    def _lista_notas(self, data):
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        for clave in ("posts", "items", "comments", "notes", "updates"):
            if isinstance(data.get(clave), list):
                return data[clave]
        return []

    def _notas_y_restacks(self, max_posts=10):
        """Notas y restacks del perfil @usuario (propios y republicados)."""
        handle = self.info.get("handle") or handle_de_substack(self.info.get("perfil") or "")
        uid = self.info.get("substack_id")
        crudos = []
        urls = []
        if uid:
            urls.append(f"https://substack.com/api/v1/profile/posts?profile_user_id={uid}&limit={max_posts * 3}")
        if handle:
            urls.append(f"https://substack.com/api/v1/user/{handle}/updates?limit={max_posts * 3}")
            self.driver.get(f"https://substack.com/@{handle}")
            time.sleep(2)
            self._cerrar_avisos()
        for u in urls:
            data = self._fetch_json(u)
            crudos.extend(self._lista_notas(data))
        if not crudos and handle:
            try:
                crudos = self.driver.execute_script("""
                    return [...document.querySelectorAll('a[href*="/p/"], a[href*="/note/"]')].slice(0, 40)
                        .map(a => ({url: a.href, body: (a.innerText || '').slice(0, 400)}));
                """) or []
            except Exception:
                crudos = []
        nombre = self.info.get("nombre") or ""
        perfil = self.info.get("perfil") or ""
        return posts_desde_notas(crudos, perfil, nombre, max_posts)

    def _leer_cuerpo_post(self, post):
        href = post.get("url_publicacion") or ""
        if not href:
            return post
        try:
            self.driver.get(href)
            time.sleep(2)
            self._cerrar_avisos()
            expandir_ver_mas(self.driver)
            extra = self.driver.execute_script("""
                const art = document.querySelector('article, .available-content, [data-testid="post"]')
                    || document.body;
                const time = document.querySelector('time');
                const imgs = [...art.querySelectorAll('img')].filter(img =>
                    (img.naturalWidth || img.width || 0) > 80);
                const alts = imgs.map(img => (img.alt || '').trim()).filter(t => t.length > 4);
                const caps = [...art.querySelectorAll('figcaption, .caption, [class*="caption"]')]
                    .map(n => (n.innerText || '').trim()).filter(t => t.length > 4);
                const cuerpo = (document.body.innerText || '');
                const restack = /restack/i.test(cuerpo) && /from\\s+@|de\\s+@/i.test(cuerpo);
                return {
                    texto: (art.innerText || '').slice(0, 4000),
                    datetime: time ? (time.getAttribute('datetime') || '') : '',
                    n_imagenes: imgs.length,
                    alts: alts,
                    captions: caps,
                    restack: restack
                };
            """) or {}
            from app.contenido import texto_mostrable
            crudo = extra.get("texto") or post.get("texto") or ""
            texto, estado = texto_mostrable(self.analisis._limpiar_texto(crudo, limite=2000) or crudo)
            if estado != "omitir" and texto and len(texto) > len(post.get("texto") or ""):
                post["texto"] = texto
            if extra.get("datetime"):
                post["tiempo"] = tiempo_legible(post.get("tiempo") or "", extra.get("datetime"))
            if extra.get("restack") and (post.get("tipo") or "") != "compartida":
                post["tipo"] = "compartida"
            alts = list(post.get("alts") or [])
            for a in (extra.get("alts") or []) + (extra.get("captions") or []):
                if a and a not in alts:
                    alts.append(a)
            post["alts"] = alts
            n_img = int(extra.get("n_imagenes") or 0)
            from app.imagenes_pub import capturar
            fotos = []
            try:
                art = self.driver.find_element(By.CSS_SELECTOR, "article, .available-content")
                fotos = capturar(art)
            except Exception:
                fotos = []
            if not fotos and alts:
                fotos = [{"id": "", "alt": a} for a in alts[:4]]
            if fotos:
                from app import vision_pub
                vista = vision_pub.analizar(fotos)
                fotos = [f for f in (vista.get("fotos") or fotos) if f.get("id")]
                if vista.get("texto"):
                    post["texto_imagen"] = vista["texto"]
                if vista.get("descripcion"):
                    post["descripcion_imagen"] = vista["descripcion"]
                for f in vista.get("fotos") or []:
                    if f.get("ocr") and f["ocr"] not in alts:
                        alts.append(f["ocr"])
                post["alts"] = alts
            n_img = max(n_img, len(fotos))
            post["imagenes"] = fotos
            post["n_imagenes"] = n_img
            post["tiene_imagenes"] = bool(n_img or fotos or post.get("texto_imagen"))
        except Exception as e:
            print(f"    No se abrió el post: {e}")
        return post

    def extraer_publicaciones(self, profile_url, max_posts=10):
        max_posts = tope_publicaciones(max_posts)
        if self.info.get("no_disponible"):
            print("  Sin publicaciones: el perfil no está disponible.")
            return []
        url = (self.info.get("perfil") or profile_url or "").rstrip("/") + "/"
        print(f"\nLeyendo posts y notas de {url}")
        crudos = []
        pubs = list(self.info.get("newsletters") or [])
        if "substack.com/@" not in url.replace("www.", "") and url not in pubs:
            pubs.insert(0, url)
        if not pubs:
            pubs = [url]
        vistos = set()
        for pub in pubs[:3]:
            clave = pub.rstrip("/").lower()
            if clave in vistos:
                continue
            vistos.add(clave)
            crudos.extend(self._archivo_de(pub, limite=max_posts * 3))
        publicaciones = posts_desde_archivo(
            crudos, url, self.info.get("nombre") or "", max_posts)
        notas = self._notas_y_restacks(max_posts)
        vistos_url = {(p.get("url_publicacion") or "").rstrip("/").lower() for p in publicaciones}
        for nota in notas:
            clave = (nota.get("url_publicacion") or "").rstrip("/").lower()
            if clave and clave in vistos_url:
                for p in publicaciones:
                    if (p.get("url_publicacion") or "").rstrip("/").lower() == clave:
                        p["tipo"] = nota.get("tipo") or p.get("tipo")
                        if nota.get("autor"):
                            p["autor"] = nota["autor"]
                continue
            publicaciones.append(nota)
            if clave:
                vistos_url.add(clave)
        vigentes, recientes, antiguas_seguidas = [], 0, 0
        hoy = datetime.now().date()
        for post in publicaciones:
            fecha = parse_fecha_publicacion(post.get("tiempo") or "")
            if fecha and (hoy - fecha).days > 365:
                antiguas_seguidas += 1
                if antiguas_seguidas >= 2:
                    break
                continue
            antiguas_seguidas = 0
            post = self._leer_cuerpo_post(post)
            vigentes.append(post)
            recientes += 1
            marca = "restack" if post.get("tipo") == "compartida" else "propia"
            print(f"  [{recientes} {marca}] {(post.get('texto') or '')[:60]}...")
            if recientes >= max_posts:
                break
        from app.discernimiento import sirve_post
        vigentes = elegir_publicaciones(
            self.analisis.filtrar_y_ordenar(vigentes), max_posts,
            grupo_de=lambda p: "compartida" if p.get("tipo") == "compartida" else "propia",
            es_catalogo=sirve_post, solo_utiles=True)
        from app.perfil_redes import aplicar_lo_publicado
        from app.redes_seguidas import aplicar_a_info
        self.info = aplicar_lo_publicado(self.info, vigentes)
        self.info = aplicar_a_info(self.info, posts=vigentes)
        self.analisis.info_perfil[url] = self.info
        print(f"  OK {len(vigentes)} posts de Substack")
        return vigentes[:max_posts]

    def ejecutar(self, profile_url, max_posts=10):
        if not self.iniciar_navegador():
            self.cerrar_navegador(preguntar=False)
            return {"ok": False, "motivo": "No se confirmo el acceso a Substack."}
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
        description="Substack: ficha + posts del ultimo año -> recomendaciones")
    parser.add_argument("url", help="https://substack.com/@usuario o https://usuario.substack.com/")
    parser.add_argument("--max-posts", type=int, default=10)
    args = parser.parse_args()
    bot = SubstackActivityScraper()
    try:
        resultado = bot.ejecutar(args.url, max_posts=args.max_posts)
        print(resultado.get("motivo", "Listo."))
    except Exception as e:
        bot.cerrar_navegador(preguntar=False)
        raise SystemExit(f"Error: {e}") from e
