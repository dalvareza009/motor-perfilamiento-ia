"""Seguidores, cuentas que sigue y reposts se guardan como hechos aparte."""
from app.ingesta_actividad import hechos_desde_info
from app.perfil_redes import sugerir_productos
from app.redes_seguidas import (CATEGORIAS_RED, aplicar_a_info, elegir_publicaciones,
                                formatear_seguidas, handle_de_url, hechos_de_red,
                                lista_nombres, limpiar_nombres, objetivos_de_post,
                                rankear_interacciones, rankear_reposts, tope_publicaciones,
                                urls_likes_y_seguidos)
try:
    from x_activity_scraper import armar_publicacion
except ImportError:
    armar_publicacion = None


def test_limpia_ruido_y_handle():
    assert limpiar_nombres(["Seguir", "Universidad EAFIT", "12", "Revista Semana"]) == [
        "Universidad EAFIT", "Revista Semana"]
    assert handle_de_url("https://x.com/yiosalgo76", "x") == "yiosalgo76"
    assert handle_de_url("https://www.instagram.com/ana/", "instagram") == "ana"
    assert handle_de_url("https://www.instagram.com/p/abc/", "instagram") == ""


def test_rankea_cuentas_con_mas_interaccion():
    posts = [
        {"tipo": "compartida", "autor": "Revista Semana", "texto": "Una nota larga sobre el país y la economía."},
        {"tipo": "compartida", "autor": "Revista Semana", "texto": "Otra nota larga de la misma revista."},
        {"tipo": "respuesta", "texto": "Gracias @eltiempo por el dato de hoy en Colombia",
         "contexto_social": "En respuesta a @eltiempo"},
        {"tipo": "publicacion", "autor": "Daniela Álvarez", "texto": "Hola a todos los que leen esto hoy."},
    ]
    ranking = rankear_interacciones(posts, dueno="Daniela Álvarez")
    assert ranking[0][0] == "Revista Semana" and ranking[0][1] == 2
    assert any(_n == "eltiempo" for _n, _c in ranking)
    assert objetivos_de_post(posts[3], dueno="Daniela Álvarez") == []
    assert rankear_reposts(posts, dueno="Daniela Álvarez") == [("Revista Semana", 2)]


def test_hechos_solo_seguidor_sigue_a_y_repost():
    info = aplicar_a_info(
        {"nombre": "Ana Gómez"},
        seguidores=["Carlos Pérez", "Luisa Restrepo"],
        sigue_a=["Universidad EAFIT"],
        intereses=["Federación Colombiana de Ciclismo"],
        posts=[{"tipo": "compartida", "autor": "Revista Semana",
                "texto": "Una nota larga de actualidad nacional."},
               {"tipo": "respuesta", "autor": "eltiempo",
                "texto": "Gracias por el dato de hoy en Colombia"}],
    )
    assert "2 seguidores" in info["resumen_red"]
    hechos = hechos_desde_info(info)
    por_cat = {}
    for h in hechos:
        por_cat.setdefault(h["categoria"], []).append(h["titulo"])
    assert "Carlos Pérez" in por_cat["Seguidor"]
    assert "Universidad EAFIT" in por_cat["Sigue a"]
    assert "Federación Colombiana de Ciclismo" in por_cat["Sigue a"]
    assert "Revista Semana" in por_cat["Repost"]
    assert "eltiempo" not in por_cat.get("Repost", [])
    assert "Interes" not in por_cat
    assert "Resumen red" not in por_cat
    assert "Interaccion frecuente" not in por_cat
    assert set(CATEGORIAS_RED) <= set(por_cat)
    productos = {s["titulo"] for s in sugerir_productos(hechos)}
    assert "Seguro educativo" in productos
    assert "Seguro de accidentes personales" in productos


def test_lista_vacia_no_inventa_hechos_de_red():
    assert hechos_de_red({"nombre": "Ana"}) == []
    assert hechos_de_red({"nombre": "Ana", "_red_intentada": True}) == []
    assert lista_nombres("186") == []
    assert lista_nombres("1.543") == []
    assert hechos_de_red({"nombre": "Ana", "seguidores": "186"}) == []


def test_repost_de_instagram_usa_el_autor_original():
    posts = [{
        "tipo": "compartida",
        "autor": "eltiempo",
        "texto": "Una nota larga sobre el país y la familia en Colombia hoy.",
        "url_publicacion": "https://www.instagram.com/p/abc/",
    }]
    assert rankear_reposts(posts, dueno="Ana Gómez ana")[0][0] == "eltiempo"


def test_facebook_origen_de_lo_compartido():
    cabecera = "Ana Gómez compartió una publicación de Revista Semana.\nHace 2 d"
    try:
        from facebook_activity_scraper import origen_compartida
        assert origen_compartida(cabecera, "Ana Gómez") == "Revista Semana"
        assert origen_compartida("Ana Gómez publicó una foto", "Ana Gómez") == "Ana Gómez"
    except ImportError:
        posts = [{"tipo": "compartida", "autor": "Revista Semana",
                  "texto": "Una nota larga de actualidad nacional hoy en Colombia."}]
        assert rankear_reposts(posts, dueno="Ana Gómez")[0][0] == "Revista Semana"


def test_repost_de_x_usa_el_autor_original():
    if armar_publicacion is None:
        return
    post = armar_publicacion({
        "texto": "Un texto bastante largo de otra persona sobre su familia y su trabajo.",
        "social": "Daniela Álvarez reposteó",
        "href": "https://x.com/eltiempo/status/88",
    }, "https://x.com/dani", autor="Daniela Álvarez")
    assert post["tipo"] == "compartida"
    assert post["autor"] == "eltiempo"
    assert rankear_reposts([post], dueno="Daniela Álvarez dani")[0][0] == "eltiempo"


def test_urls_facebook_de_likes():
    assert urls_likes_y_seguidos("https://www.facebook.com/ana")[0].endswith("/likes")
    assert "sk=likes" in urls_likes_y_seguidos("https://www.facebook.com/profile.php?id=5")[0]
    assert urls_likes_y_seguidos("https://www.facebook.com/ana")[-1].endswith("/followers")


def test_formatea_lista():
    assert formatear_seguidas(["EAFIT"]) == "Páginas o cuentas seguidas: EAFIT"
    assert formatear_seguidas([]) == ""


def test_extraer_red_social_existe():
    from app.redes_seguidas import extraer_red_social
    from app import redes_seguidas
    assert callable(extraer_red_social)
    assert extraer_red_social is redes_seguidas.extraer_red_social


def test_el_tope_es_el_total_no_un_cupo_por_tipo():
    assert tope_publicaciones(1) == 1
    assert tope_publicaciones(4) == 4
    assert tope_publicaciones("4") == 4
    assert tope_publicaciones(10) == 10
    assert tope_publicaciones(50) == 10
    posts = [{"tipo": "publicacion", "texto": f"p{i}"} for i in range(8)]
    posts += [{"tipo": "compartida", "texto": f"c{i}"} for i in range(8)]
    posts += [{"tipo": "respuesta", "texto": f"r{i}"} for i in range(8)]
    assert len(elegir_publicaciones(posts, 1)) == 1
    assert len(elegir_publicaciones(posts, 4)) == 4
    assert len(elegir_publicaciones(posts, 10)) == 10
    catalogo = elegir_publicaciones(
        posts + [{"tipo": "compartida", "texto": "universidad hija seguro"}],
        1,
        es_catalogo=lambda p: "universidad" in p["texto"],
    )
    assert len(catalogo) == 1
    assert "universidad" in catalogo[0]["texto"]


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
