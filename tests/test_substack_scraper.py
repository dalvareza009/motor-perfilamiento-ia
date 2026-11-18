"""Pruebas de Substack, sin navegador.

Ejecutar:  python -m tests.test_substack_scraper
"""
from app.contenido import describir_publicacion
from app.gustos import senales
from app.ingesta_actividad import hechos_desde_info
from app.perfil_redes import clasificar_url, detectar_otras_redes
from app.redes_seguidas import handle_de_url
from app.vision_pub import frase
from substack_activity_scraper import (ficha_desde_api, handle_de_substack, parsear_ficha_substack,
                                       posts_desde_archivo, posts_desde_notas, url_de_publicacion)


def test_acepta_perfil_y_newsletter():
    assert clasificar_url("https://substack.com/@ana.gomez")[1] == "https://substack.com/@ana.gomez"
    assert clasificar_url("https://www.substack.com/@Ana.Gomez/notes")[1] == "https://substack.com/@ana.gomez"
    assert clasificar_url("https://ana-gomez.substack.com/p/mi-post")[1] == "https://ana-gomez.substack.com/"
    assert clasificar_url("https://substack.com/") is None
    assert clasificar_url("https://substack.com/explore") is None
    assert clasificar_url("https://www.substack.com/home") is None


def test_handle_sale_del_perfil_y_del_newsletter():
    assert handle_de_substack("https://substack.com/@ana.gomez") == "ana.gomez"
    assert handle_de_url("https://substack.com/@ana.gomez", "substack") == "ana.gomez"
    assert handle_de_url("https://ana-gomez.substack.com/", "substack") == "ana-gomez"
    assert url_de_publicacion("https://ana.substack.com/p/hola-mundo?utm=1") == "https://ana.substack.com/p/hola-mundo"


def test_la_ficha_saca_bio_trabajo_y_otra_red():
    info = parsear_ficha_substack("""
    Ana Gómez
    @ana.gomez
    Escribo sobre finanzas familiares en Colombia
    Mamá de dos
    Medellín
    https://www.linkedin.com/in/ana-gomez/
    Subscribe
    Activity
    """)
    assert info["nombre"] == "Ana Gómez"
    mezcla = " ".join(p for p in (info.get("bio"), info.get("titular"), info.get("experiencia")) if p).lower()
    assert "finanzas" in mezcla
    assert "hija" in (info.get("familia") or info.get("estado_civil") or info.get("bio") or "").lower() or "mamá" in (info.get("familia") or info.get("bio") or "").lower()
    redes = detectar_otras_redes("https://www.linkedin.com/in/ana-gomez/", "substack")
    assert any(r["red"] == "linkedin" for r in redes)


def test_api_llena_newsletter_y_twitter():
    info = ficha_desde_api({
        "name": "Ana Gómez",
        "handle": "ana",
        "bio": "Periodista en Bogotá. Mamá de Valentina.",
        "twitter_screen_name": "ana_g",
        "publicationUsers": [{"publication": {"name": "Cartas de Ana", "subdomain": "cartasdeana"}}],
    }, "https://substack.com/@ana")
    assert info["nombre"] == "Ana Gómez"
    assert "Cartas de Ana" in (info.get("experiencia") or "")
    assert "cartasdeana.substack.com" in " ".join(info.get("newsletters") or [])
    urls = [x["url"] for x in (info.get("otras_redes") or [])]
    assert any("x.com/ana_g" in u for u in urls)
    hechos = hechos_desde_info(info)
    assert any(h["categoria"] == "Descripcion" for h in hechos)


def test_el_archivo_arma_posts_y_marca_pago():
    posts = posts_desde_archivo([
        {"id": 1, "title": "Cómo ahorrar", "subtitle": "Hábitos",
         "truncated_body_text": "Empiezo por el presupuesto familiar.",
         "canonical_url": "https://ana.substack.com/p/ahorrar",
         "post_date": "2026-10-01T12:00:00.000Z", "audience": "everyone"},
        {"id": 2, "title": "Solo para suscriptores", "subtitle": "",
         "truncated_body_text": "Vista corta.",
         "canonical_url": "https://ana.substack.com/p/pago",
         "post_date": "2026-10-02T12:00:00.000Z", "audience": "only_paid"},
    ], "https://ana.substack.com/", "Ana Gómez", max_posts=10)
    assert len(posts) == 2
    assert posts[0]["tipo"] == "publicacion"
    assert "presupuesto" in posts[0]["texto"]
    assert "pago" in posts[1]["texto"].lower()


def test_restack_queda_como_compartida():
    posts = posts_desde_notas([{
        "id": 9,
        "body": "Esto hay que leerlo",
        "restacked_post": {
            "title": "Cómo armar un presupuesto familiar",
            "subtitle": "Ahorro",
            "truncated_body_text": "Empieza por el gasto mensual.",
            "canonical_url": "https://otro.substack.com/p/presupuesto",
            "publishedBylines": [{"name": "Luis Pérez"}],
        },
        "date": "2026-10-04T12:00:00.000Z",
    }], "https://substack.com/@ana", "Ana Gómez")
    assert posts[0]["tipo"] == "compartida"
    assert posts[0]["autor"] == "Luis Pérez"
    assert "presupuesto" in posts[0]["texto"].lower()
    d = describir_publicacion(posts[0])
    assert "restack" in d["resumen"].lower()
    assert "finanza" in d["resumen"].lower()


def test_la_imagen_con_texto_alimenta_gustos():
    assert "ahorro" in frase("AHORRO E INVERSIÓN 2026", "", ["Finanzas"]).lower()
    d = describir_publicacion({
        "texto": "Mira esta infografía.",
        "tipo": "publicacion",
        "tiene_imagenes": True,
        "n_imagenes": 1,
        "texto_imagen": "Presupuesto familiar y ahorro en Colombia",
        "descripcion_imagen": "En la imagen se lee: «Presupuesto familiar y ahorro en Colombia». Tema visual: finanzas.",
    })
    assert "en la imagen se lee" in d["resumen"].lower()
    assert "finanza" in d["resumen"].lower()
    hallado = senales({}, [{
        "texto": "Mira.",
        "tipo": "compartida",
        "autor": "Otro newsletter",
        "texto_imagen": "Cicla, maratón y gimnasio este domingo",
    }])
    assert "Deportes" in hallado


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
