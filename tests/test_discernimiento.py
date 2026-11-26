"""Solo entra al perfil lo que ayuda a ofertar un seguro.

Ejecutar:  python -m tests.test_discernimiento
"""
from app.discernimiento import evaluar, ficha_necesaria, filtrar_posts, sirve_post
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


def test_la_ficha_clara_se_aprueba_sola_y_el_resto_no():
    assert ficha_necesaria("Trabajo", "Analista de datos en Global Seguros") == "Trabajo"
    assert ficha_necesaria("Experiencia", "Trabajé en Bancolombia como cajera hasta 2020") == "Experiencia"
    assert ficha_necesaria("Descripcion", "Estudié ingeniería en la Universidad EAFIT") == "Estudios"
    assert ficha_necesaria("Informacion", "Estoy casada") == "Estado civil"
    assert ficha_necesaria("Descripcion", "Soy de Cali") == "Origen"
    assert ficha_necesaria("Ubicacion", "Vivo en Medellín") == "Ubicacion"
    assert ficha_necesaria("Ubicacion", "Medellín, Antioquia, Colombia") == "Ubicacion"
    assert ficha_necesaria("Edad", "Tengo 29 años") == "Edad"
    assert ficha_necesaria("Cursos", "Hice un curso de Excel en Platzi") == ""
    assert ficha_necesaria("Descripcion", "Trabajo en equipo los viernes") == ""
    assert ficha_necesaria("Descripcion", "Busco empleo desde marzo") == ""
    assert ficha_necesaria("Ubicacion", "De vacaciones en Cartagena con mi hija") == ""
    assert ficha_necesaria("Edad", "Mi hija tiene 8 años") == ""
    assert ficha_necesaria("Ingresos", "Me subieron el salario este año") == ""
    assert ficha_necesaria("Sigue a", "Sigue a Bancolombia") == ""
    assert ficha_necesaria("Producto sugerido", "Seguro de vida") == ""


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
