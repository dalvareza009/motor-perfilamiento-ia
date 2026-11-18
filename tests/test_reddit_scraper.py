"""Pruebas de Reddit, sin navegador.

Ejecutar:  python -m tests.test_reddit_scraper
"""
from app.perfil_redes import clasificar_url
from app.redes_seguidas import handle_de_url
from reddit_activity_scraper import (ficha_desde_api, handle_de_reddit, parsear_ficha_reddit,
                                     posts_desde_listing)


def test_acepta_perfil_y_rechaza_subreddit():
    assert clasificar_url("https://www.reddit.com/user/ana_g/")[1] == "https://www.reddit.com/user/ana_g/"
    assert clasificar_url("https://www.reddit.com/u/Ana_g/submitted")[1] == "https://www.reddit.com/user/Ana_g/"
    assert clasificar_url("https://old.reddit.com/user/ana_g")[1] == "https://www.reddit.com/user/ana_g/"
    assert clasificar_url("https://www.reddit.com/r/personalfinance/") is None
    assert clasificar_url("https://www.reddit.com/") is None
    assert handle_de_reddit("https://www.reddit.com/user/ana_g/") == "ana_g"
    assert handle_de_url("https://www.reddit.com/user/ana_g/", "reddit") == "ana_g"


def test_ficha_saca_bio_y_familia():
    info = parsear_ficha_reddit("""
    Ana Gómez
    u/ana_g
    Mamá de dos en Medellín. Escribo sobre ahorro.
    """, perfil="https://www.reddit.com/user/ana_g/")
    assert "Ana" in info["nombre"]
    assert "ahorro" in (info.get("bio") or "").lower() or "medell" in (info.get("ubicacion") or info.get("bio") or "").lower()


def test_api_llena_nombre_y_bio():
    info = ficha_desde_api({
        "data": {
            "name": "ana_g",
            "subreddit": {
                "title": "Ana Gómez",
                "public_description": "Mamá en Bogotá. Me interesa el presupuesto familiar.",
            },
        },
    }, "https://www.reddit.com/user/ana_g/")
    assert info["nombre"] == "Ana Gómez"
    assert "presupuesto" in (info.get("bio") or "").lower() or "mam" in (info.get("familia") or info.get("bio") or "").lower()


def test_listing_arma_post_con_subreddit():
    posts = posts_desde_listing({
        "data": {"children": [
            {"kind": "t3", "data": {
                "id": "abc", "title": "Cómo armar un presupuesto",
                "selftext": "Empiezo por el ahorro mensual.",
                "subreddit": "personalfinance",
                "permalink": "/r/personalfinance/comments/abc/presupuesto/",
                "created_utc": 1762900000, "over_18": False,
            }},
            {"kind": "t1", "data": {
                "id": "xyz", "body": "lol",
                "subreddit": "funny", "over_18": False,
                "created_utc": 1762900000,
            }},
        ]},
    }, "https://www.reddit.com/user/ana_g/", "Ana Gómez")
    assert posts[0]["subreddit"] == "personalfinance"
    assert "presupuesto" in posts[0]["texto"].lower()
    assert posts[1]["tipo"] == "comentario"


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
