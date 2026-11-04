"""Pruebas del despliegue (sesión firmada, cookies de entorno, sin login manual en nube).

Ejecutar:  python -m tests.test_despliegue
"""
import json
import os
from pathlib import Path

from app import runtime_nube, sesion_token
from x_activity_scraper import XActivityScraper


def test_sesion_firmada_redonda():
    token = sesion_token.emitir("daniela", "admin")
    leida = sesion_token.leer(token)
    assert leida == {"usuario": "daniela", "rol": "admin"}
    assert sesion_token.leer("basura") is None
    assert sesion_token.leer("") is None


def test_en_vercel_no_hay_login_manual(monkeypatch=None):
    prev = os.environ.get("VERCEL")
    os.environ["VERCEL"] = "1"
    try:
        assert runtime_nube.en_nube() is True
        assert runtime_nube.login_manual_permitido() is False
        bot = XActivityScraper()
        assert bot.esperar_login_manual("prueba") is False
    finally:
        if prev is None:
            os.environ.pop("VERCEL", None)
        else:
            os.environ["VERCEL"] = prev


def test_materializa_cookies_desde_env():
    import tempfile
    os.environ["COOKIES_X_JSON"] = json.dumps([{"name": "auth_token", "value": "x"}])
    with tempfile.TemporaryDirectory() as tmp:
        try:
            escritos = runtime_nube.materializar_cookies(tmp)
            assert "x_cookies.json" in escritos
            datos = json.loads((Path(tmp) / "x_cookies.json").read_text(encoding="utf-8"))
            assert datos[0]["name"] == "auth_token"
        finally:
            os.environ.pop("COOKIES_X_JSON", None)


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
