"""Fotos de las publicaciones: se capturan en el Chrome de la sesión y se muestran en la ficha.

No se depende del CDN (caduca o pide cookie). Se toma una captura de cada imagen
del post y se guarda en disco. El revisor las ve en «Revisión contenido».
"""
import hashlib
import json
import re
from pathlib import Path

TOPE = 4
MIN_ANCHO = 80
MIN_BYTES = 1200
CARPETA = Path(__file__).resolve().parents[1] / "data" / "media_publicaciones"
_ID = re.compile(r"^[a-f0-9]{16,64}$")
_RUIDO_ALT = re.compile(
    r"(foto de perfil|profile picture|imagen de perfil|avatar|"
    r"me gusta|comentar|compartir|like|comment|emoji|sticker)",
    re.I,
)
_RUIDO_SRC = (
    "emoji", "static.xx.fbcdn", "/rsrc.php", "sprite", "data:image/svg",
    "profile_pic", "scontent.*_s.",
)


def _asegurar():
    CARPETA.mkdir(parents=True, exist_ok=True)
    return CARPETA


def guardar_bytes(png):
    """Guarda PNG y devuelve el id. Vacío si el archivo no sirve."""
    raw = bytes(png or b"")
    if len(raw) < MIN_BYTES:
        return ""
    ident = hashlib.sha256(raw).hexdigest()[:16]
    destino = _asegurar() / f"{ident}.png"
    if not destino.exists():
        destino.write_bytes(raw)
    return ident


def ruta(ident):
    if not ident or not _ID.match(ident):
        return None
    p = CARPETA / f"{ident}.png"
    return p if p.is_file() else None


def parsear(valor):
    """Texto JSON o lista -> [{id, alt}]."""
    if isinstance(valor, list):
        crudos = valor
    elif isinstance(valor, str) and valor.strip().startswith("["):
        try:
            crudos = json.loads(valor)
        except Exception:
            return []
    else:
        return []
    salida = []
    for item in crudos or []:
        if not isinstance(item, dict):
            continue
        ident = str(item.get("id") or "").strip()
        if not ident:
            continue
        salida.append({"id": ident, "alt": (item.get("alt") or "").strip()[:180]})
    return salida


def dump(imagenes):
    return json.dumps(parsear(imagenes), ensure_ascii=False)


def para_api(valor):
    return parsear(valor)


def capturar(contenedor, tope=TOPE):
    """Captura hasta `tope` fotos visibles de un post (Webelement Selenium)."""
    if contenedor is None:
        return []
    from selenium.webdriver.common.by import By

    salida, vistos = [], set()
    try:
        imgs = contenedor.find_elements(By.TAG_NAME, "img")
    except Exception:
        return []
    for im in imgs:
        if len(salida) >= tope:
            break
        try:
            tam = im.size or {}
            ancho = int(tam.get("width") or 0)
            alto = int(tam.get("height") or 0)
            if ancho < MIN_ANCHO or alto < 50:
                continue
            src = (im.get_attribute("currentSrc") or im.get_attribute("src") or "").lower()
            alt = (im.get_attribute("alt") or "").strip()
            if any(p in src for p in _RUIDO_SRC):
                continue
            if alt and _RUIDO_ALT.search(alt):
                continue
            png = im.screenshot_as_png
            ident = guardar_bytes(png)
            if not ident or ident in vistos:
                continue
            vistos.add(ident)
            salida.append({"id": ident, "alt": alt[:180]})
        except Exception:
            continue
    return salida
