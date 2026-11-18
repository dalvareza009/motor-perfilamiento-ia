"""Solo entra al perfil lo que ayuda a ofertar un seguro.

Ejecutar:  python -m tests.test_discernimiento
"""
from app.discernimiento import evaluar, filtrar_posts, sirve_post
from app.gustos import hechos_de_gustos


def test_meme_y_clima_no_entran():
    assert evaluar("Feliz viernes equipo")["sirve"] is False
    assert evaluar("Hoy el clima estuvo nublado durante toda la tarde")["sirve"] is False
    assert evaluar("lol this", subreddit="memes")["sirve"] is False
    assert evaluar("3 karma cake day")["sirve"] is False


def test_familia_ahorro_y_moto_si_entran():
    assert evaluar("Celebramos el año de mi hija en el colegio")["sirve"] is True
    assert "familia_hijos" in evaluar("Celebramos el año de mi hija en el colegio")["parametros"]
    finanzas = evaluar("Empecé un plan de ahorro e inversión este año")
    assert finanzas["sirve"] and "Seguro renta voluntaria" in finanzas["productos"]
    moto = evaluar("Salí en moto con el grupo de ciclismo")
    assert moto["sirve"] and "Seguro de accidentes personales" in moto["productos"]


def test_subreddit_de_finanzas_cuenta_aunque_el_texto_sea_corto():
    r = evaluar("pregunta", subreddit="personalfinance")
    assert r["sirve"] is True
    assert "ahorro_inversion" in r["parametros"]


def test_filtra_el_lote_y_deja_la_senal():
    posts = [
        {"texto": "Feliz viernes", "tipo": "publicacion"},
        {"texto": "Trabajo como analista en Global Seguros", "tipo": "publicacion"},
        {"texto": "meme", "subreddit": "funny", "tipo": "comentario"},
    ]
    utiles = filtrar_posts(posts)
    assert len(utiles) == 1
    assert sirve_post(utiles[0])
    assert "analista" in utiles[0]["texto"]


def test_intereses_de_vida_tambien_cuentan_para_acercarnos():
    serie = evaluar("Nueva serie este fin de semana en la plataforma.")
    assert serie["sirve"] is True
    assert "intereses_de_vida" in serie["parametros"]
    hechos = hechos_de_gustos(
        {"nombre": "Ana", "sigue_a": ["Netflix", "Bancolombia"]},
    )
    titulos = {h["titulo"] for h in hechos}
    assert "Gusto · Finanzas" in titulos
    assert "Gusto · Entretenimiento" in titulos


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
