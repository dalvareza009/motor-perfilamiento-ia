"""Adaptaciones cuando el motor corre en Vercel u otro contenedor (sin Chrome de escritorio)."""
import json
import os
from pathlib import Path


def en_nube():
    return bool(os.getenv("VERCEL") or os.getenv("SCRAPE_HEADLESS"))


def login_manual_permitido():
    flag = (os.getenv("SCRAPE_MANUAL_LOGIN") or "").strip().lower()
    if flag in ("0", "false", "no"):
        return False
    if flag in ("1", "true", "si", "sí", "yes"):
        return True
    return not en_nube()


def aplicar_chrome(options):
    binario = os.getenv("CHROME_BIN") or os.getenv("CHROMIUM_PATH")
    if binario:
        options.binary_location = binario
    if en_nube():
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
    return options


def crear_driver(options):
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service

    aplicar_chrome(options)
    driver = os.getenv("CHROMEDRIVER")
    if driver:
        return webdriver.Chrome(service=Service(driver), options=options)
    return webdriver.Chrome(options=options)


_COOKIES_ENV = (
    ("COOKIES_X_JSON", "x_cookies.json"),
    ("COOKIES_LINKEDIN_JSON", "linkedin_cookies.json"),
    ("COOKIES_FACEBOOK_JSON", "facebook_cookies.json"),
    ("COOKIES_INSTAGRAM_JSON", "instagram_cookies.json"),
)


def materializar_cookies(raiz=None):
    """Escribe los JSON de cookies desde variables de entorno (secretos de Vercel)."""
    base = Path(raiz) if raiz else Path(__file__).resolve().parents[1]
    escritos = []
    for variable, nombre in _COOKIES_ENV:
        bruto = os.getenv(variable)
        if not bruto or not bruto.strip():
            continue
        try:
            datos = json.loads(bruto)
        except json.JSONDecodeError:
            print(f"Cookie {nombre}: {variable} no es JSON válido; se ignora.")
            continue
        destino = base / nombre
        destino.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        escritos.append(nombre)
    return escritos
