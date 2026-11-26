# reddit_activity_scraper.py
"""
Extractor de Reddit: ficha (nombre, bio), posts y comentarios útiles.
Solo se queda lo que nutre el perfil de seguro (discernimiento).

Chrome con ``chrome_reddit_profile/`` y ``reddit_cookies.json``.
Los perfiles públicos se leen sin login; si Reddit pide entrar, el
navegador queda abierto hasta que confirmes.

Uso:
    python reddit_activity_scraper.py https://www.reddit.com/user/usuario
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
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from linkedin_activity_scraper import (LinkedInActivityScraper, extraer_red_de,
                                       parse_fecha_publicacion)
from app.redes_seguidas import elegir_publicaciones, tope_publicaciones
from app.discernimiento import filtrar_posts, sirve_post

MARCAS_MURO = ("/login", "/register", "reddit.com/login")
REDDIT_RESERVADOS = {
    "popular", "all", "reddit", "admin", "login", "register", "premium",
    "coins", "gallery", "explore", "search", "message", "chat", "settings",
    "notifications", "submit", "r", "user", "u", "home", "best", "hot",
}
RUIDO_FICHA = {
    "create post", "crear publicación", "karma", "cake day", "moderator",
    "joined", "se unió", "follow", "seguir", "chat", "mensaje", "message",
}


def handle_de_reddit(url):
    partes = [p for p in urlparse(url or "").path.split("/") if p]
    if len(partes) >= 2 and partes[0].lower() in ("user", "u"):
        h = partes[1].strip()
        if h.lower() not in REDDIT_RESERVADOS:
            return h
    return ""


def url_perfil_reddit(url):
    from app.perfil_redes import clasificar_url
    c = clasificar_url(url or "")
    return c[1] if c and c[0] == "reddit" else (url or "").split("?")[0].rstrip("/") + "/"


def es_no_disponible(texto):
    t = (texto or "").lower()
    return any(m in t for m in (
        "sorry, nobody on reddit goes by that name",
        "page not found", "this account has been banned",
        "this account is suspended", "user not found",
    ))


def _n(texto):
    return re.sub(r"\s+", " ", str(texto or "")).strip()


def parsear_ficha_reddit(cuerpo, nombre_conocido="", perfil=""):
    from app.perfil_redes import anexar_otras_redes, aplicar_frase

    handle = handle_de_reddit(perfil)
    info = {
        "nombre": nombre_conocido, "titular": "", "ubicacion": "", "experiencia": "",
        "educacion": "", "estado_civil": "", "familia": "", "bio": "", "handle": handle,
        "perfil": perfil, "sigue_a": [],
    }
    vistos = set()
    for cruda in (cuerpo or "").splitlines():
        t = _n(cruda)
        baja = t.lower()
        if len(t) < 3 or baja in RUIDO_FICHA or baja in vistos:
            continue
        vistos.add(baja)
        if re.fullmatch(r"u/[A-Za-z0-9_-]{2,30}", t) and not info["handle"]:
            info["handle"] = t[2:]
            continue
        if not info["nombre"] and 3 <= len(t) <= 80 and t.lower() not in RUIDO_FICHA:
            if not re.match(r"^(r/|http|karma|\d)", baja):
                info["nombre"] = t[:120]
                continue
        aplicar_frase(info, t, desde_publicacion=False)
        if len(t) >= 24 and not info.get("bio"):
            info["bio"] = t[:400]
        info = anexar_otras_redes(info, t, "reddit", perfil)
    if not info.get("nombre"):
        info["nombre"] = info.get("handle") or ""
    return info


def ficha_desde_api(data, perfil=""):
    from app.perfil_redes import anexar_otras_redes, aplicar_frase

    bloque = data.get("data") if isinstance(data, dict) else {}
    if not isinstance(bloque, dict):
        bloque = {}
    sub = bloque.get("subreddit") if isinstance(bloque.get("subreddit"), dict) else {}
    handle = (bloque.get("name") or handle_de_reddit(perfil) or "").lstrip("u/")
    nombre = _n(sub.get("title") or "") or handle
    bio = _n(sub.get("public_description") or bloque.get("public_description") or "")
    info = parsear_ficha_reddit("\n".join(p for p in (nombre, bio) if p), nombre, perfil)
    info["handle"] = handle
    info["nombre"] = nombre or handle
    if bio:
        info["bio"] = bio[:400]
        aplicar_frase(info, bio, desde_publicacion=False)
    info = anexar_otras_redes(info, bio, "reddit", perfil)
    return info


def _utc_a_tiempo(valor):
    try:
        ts = float(valor)
        return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        return ""


def posts_desde_listing(data, perfil, nombre="", tipo="publicacion"):
    """submitted.json o comments.json -> publicaciones del motor."""
    bloque = data.get("data") if isinstance(data, dict) else data
    hijos = []
    if isinstance(bloque, dict):
        hijos = bloque.get("children") or []
    elif isinstance(data, list):
        hijos = data
    salida = []
    for item in hijos:
        d = item.get("data") if isinstance(item, dict) else item
        if not isinstance(d, dict):
            continue
        if d.get("over_18") or d.get("removed_by_category"):
            continue
        titulo = _n(d.get("title") or d.get("link_title") or "")
        cuerpo = _n(d.get("selftext") or d.get("body") or "")
        sub = _n(d.get("subreddit") or "")
        partes = [p for p in (f"r/{sub}" if sub else "", titulo, cuerpo) if p]
        texto = "\n".join(partes)
        if not texto:
            continue
        permalink = d.get("permalink") or ""
        href = ("https://www.reddit.com" + permalink) if permalink.startswith("/") else (d.get("url") or "")
        clase = "comentario" if (tipo == "comentario" or item.get("kind") == "t1") else "publicacion"
        salida.append({
            "perfil": perfil, "urn": str(d.get("id") or "N/A"),
            "url_publicacion": href, "tipo": clase, "autor": nombre or handle_de_reddit(perfil),
            "texto": texto[:2000], "tiempo": _utc_a_tiempo(d.get("created_utc")),
            "hashtags": "", "enlaces": href, "reacciones": "", "comentarios": "",
            "alts": [], "imagenes": [], "n_imagenes": 0, "tiene_imagenes": False,
            "subreddit": sub, "fecha_extraccion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    return salida


class RedditActivityScraper:
    def __init__(self, cookie_file="reddit_cookies.json",
                 profile_dir="chrome_reddit_profile", confirmar_login=None):
        self.cookie_file = Path(cookie_file)
        self.profile_dir = Path(profile_dir).resolve()
        self.confirmar_login = confirmar_login
        self.driver = None
        self.info = {}
        self.analisis = LinkedInActivityScraper(
            cookie_file="linkedin_cookies.json", profile_dir="chrome_reddit_profile")
        self.analisis.prefijo_archivos = "reddit"
        self.analisis.peso_compartida = self.analisis.peso_propia
        self.analisis.priorizar_propias = False

    def _sanitizar(self, raw):
        if not isinstance(raw, dict) or not raw.get("name") or "value" not in raw:
            return None
        domain = str(raw.get("domain") or ".reddit.com")
        if "reddit.com" not in domain:
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
        return "reddit_session" in nombres or not self._en_muro_de_login()

    def guardar_cookies(self):
        if self.driver is None:
            return
        try:
            cookies = [c for c in self.driver.get_cookies()
                       if "reddit.com" in (c.get("domain") or "")]
            self.cookie_file.write_text(json.dumps(cookies, indent=2, ensure_ascii=False),
                                        encoding="utf-8")
            print(f"Cookies de Reddit guardadas ({len(cookies)})")
        except Exception as e:
            print(f"No se pudieron guardar las cookies: {e}")

    def _cerrar_avisos(self):
        try:
            self.driver.execute_script("""
                const textos = ['accept', 'aceptar', 'got it', 'continue', 'continuar',
                                'allow all cookies', 'accept all', 'aceptar todo'];
                for (const b of document.querySelectorAll('button, [role="button"]')) {
                    const t = (b.innerText || '').trim().toLowerCase();
                    if (textos.includes(t)) b.click();
                }
            """)
        except Exception:
            pass

    def esperar_login_manual(self, contexto=""):
        print("\nReddit esta pidiendo iniciar sesion. El navegador queda abierto:")
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
            self.driver.get("https://www.reddit.com/")
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
        self.driver.get("https://www.reddit.com/")
        time.sleep(3)
        self._cerrar_avisos()
        if self.cookie_file.is_file():
            try:
                crudo = json.loads(self.cookie_file.read_text(encoding="utf-8"))
                if isinstance(crudo, dict):
                    crudo = crudo.get("cookies", [])
                for raw in crudo or []:
                    c = self._sanitizar(raw)
                    if c:
                        try:
                            self.driver.add_cookie(c)
                        except Exception:
                            pass
                self.driver.get("https://www.reddit.com/")
                time.sleep(2)
                if not self._en_muro_de_login():
                    print("Sesion de Reddit activa (cookies)")
                    self.guardar_cookies()
                    return True
            except Exception as e:
                print(f"Cookies de Reddit no utilizables: {e}")
        if not self._en_muro_de_login():
            return True
        return self.esperar_login_manual("inicio del bot de Reddit")

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
            print(f"  API Reddit no respondió: {e}")
            return None

    def extraer_informacion_perfil(self, profile_url):
        print(f"\nLeyendo primero la ficha de Reddit: {profile_url}")
        url = url_perfil_reddit(profile_url)
        self.driver.get(url)
        time.sleep(3)
        self._cerrar_avisos()
        if self._en_muro_de_login():
            if not self.esperar_login_manual(url):
                return {}
            self.driver.get(url)
            time.sleep(3)
        handle = handle_de_reddit(url)
        data = self._fetch_json(f"https://www.reddit.com/user/{handle}/about.json") if handle else None
        info = ficha_desde_api(data, url) if data else {}
        if not info.get("nombre"):
            try:
                cuerpo = self.driver.find_element(By.TAG_NAME, "body").text or ""
            except Exception:
                cuerpo = ""
            if es_no_disponible(cuerpo):
                info = {"perfil": url, "no_disponible": True, "nombre": "", "handle": handle}
            else:
                info = parsear_ficha_reddit(cuerpo[:3500], info.get("nombre") or "", url)
        info["perfil"] = url
        info["handle"] = info.get("handle") or handle
        if info.get("no_disponible"):
            print("  Reddit no muestra este perfil.")
        else:
            print(f"  OK {info.get('nombre') or handle or 'Perfil de Reddit'}")
        if not info.get("no_disponible"):
            info = extraer_red_de(self.driver, "reddit", url, info)
        self.info = info
        self.analisis.info_perfil[url] = info
        return info

    def extraer_publicaciones(self, profile_url, max_posts=10):
        max_posts = tope_publicaciones(max_posts)
        if self.info.get("no_disponible"):
            print("  Sin publicaciones: el perfil no está disponible.")
            return []
        handle = self.info.get("handle") or handle_de_reddit(profile_url)
        url = url_perfil_reddit(profile_url)
        print(f"\nLeyendo posts y comentarios útiles de {url}")
        crudos = []
        if handle:
            enviados = self._fetch_json(
                f"https://www.reddit.com/user/{handle}/submitted.json?limit={max_posts * 3}")
            crudos.extend(posts_desde_listing(enviados or {}, url, self.info.get("nombre") or handle))
            comentarios = self._fetch_json(
                f"https://www.reddit.com/user/{handle}/comments.json?limit={max_posts * 3}")
            crudos.extend(posts_desde_listing(
                comentarios or {}, url, self.info.get("nombre") or handle, tipo="comentario"))
        utiles = filtrar_posts(crudos)
        vigentes, antiguas = [], 0
        hoy = datetime.now().date()
        for post in utiles:
            fecha = parse_fecha_publicacion(post.get("tiempo") or "")
            if fecha and (hoy - fecha).days > 365:
                antiguas += 1
                if antiguas >= 3:
                    break
                continue
            antiguas = 0
            vigentes.append(post)
        vigentes = elegir_publicaciones(
            self.analisis.filtrar_y_ordenar(vigentes), max_posts,
            grupo_de=lambda p: "comentario" if p.get("tipo") == "comentario" else "propia",
            es_catalogo=sirve_post, solo_utiles=True)
        subs = []
        for p in vigentes:
            s = (p.get("subreddit") or "").strip()
            if s and s not in subs:
                subs.append(s)
        if subs:
            actuales = list(self.info.get("sigue_a") or [])
            for s in subs:
                nombre = f"r/{s}"
                if nombre not in actuales:
                    actuales.append(nombre)
            self.info["sigue_a"] = actuales
        from app.perfil_redes import aplicar_lo_publicado
        from app.redes_seguidas import aplicar_a_info
        self.info = aplicar_lo_publicado(self.info, vigentes)
        self.info = aplicar_a_info(self.info, posts=vigentes)
        self.analisis.info_perfil[url] = self.info
        print(f"  OK {len(vigentes)} piezas útiles de Reddit")
        return vigentes[:max_posts]

    def ejecutar(self, profile_url, max_posts=10):
        if not self.iniciar_navegador():
            self.cerrar_navegador(preguntar=False)
            return {"ok": False, "motivo": "No se confirmo el acceso a Reddit."}
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
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="https://www.reddit.com/user/usuario")
    parser.add_argument("--max", type=int, default=10)
    args = parser.parse_args()
    bot = RedditActivityScraper()
    print(bot.ejecutar(args.url, max_posts=args.max))
