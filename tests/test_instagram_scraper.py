"""Pruebas de la ficha de Instagram, sin navegador.

Ejecutar:  python -m tests.test_instagram_scraper
"""
import tempfile
from pathlib import Path

from app.ingesta_actividad import hechos_desde_info
from app.perfil_redes import sugerir_productos
from instagram_activity_scraper import (alt_util, caption_de_publicacion, es_cuenta_privada,
                                        es_repost, incorporar_datos_importantes,
                                        parsear_ficha_instagram, tiempo_legible, url_de_publicacion)


FICHA = """
daa0926
Seguir
Mensaje
128
publicaciones
1.543
seguidores
890
seguidos
Daniela Álvarez
Mamá de una hija
Autónoma
Universidad EAFIT
Vive en Medellín
(2026-09-01 - None)
Ver traducción
"""


def test_la_ficha_separa_familia_trabajo_estudios_y_quita_fechas():
    info = parsear_ficha_instagram(FICHA)
    assert info["nombre"] == "Daniela Álvarez"
    assert info["seguidores"] == "1.543"
    assert "hija" in info["estado_civil"].lower()
    assert "autónoma" in info["experiencia"].lower()
    assert "Universidad EAFIT" in info["educacion"]
    assert "Medellín" in info["ubicacion"]
    assert "Seguir" not in info["acerca"]
    assert "2026-09-01" not in info["acerca"]
    assert "None" not in info["acerca"]
    hechos = hechos_desde_info(info)
    productos = {p["titulo"] for p in sugerir_productos(hechos)}
    assert "Seguro de vida" in productos
    assert "Seguro educativo" in productos


def test_cuenta_privada_no_trae_publicaciones():
    assert es_cuenta_privada("Esta cuenta es privada\nSigue esta cuenta para ver sus fotos y videos.")
    info = parsear_ficha_instagram("Daniela Álvarez\nEsta cuenta es privada\nMamá de una hija")
    assert info["privado"] is True
    assert "hija" in info["estado_civil"].lower()


def test_el_tiempo_de_un_post_no_queda_en_iso():
    assert tiempo_legible("3 sem", "2026-09-01T00:00:00Z") == "3 sem"
    assert tiempo_legible("", "2026-09-01T00:00:00.000Z") == "1 de septiembre de 2026"
    assert "T00:00:00" not in tiempo_legible("2026-09-01T00:00:00Z", "")
    assert url_de_publicacion("https://www.instagram.com/p/ABC123/?hl=es") == "https://www.instagram.com/p/ABC123/"
    assert url_de_publicacion("https://www.instagram.com/reel/XYZ/") == "https://www.instagram.com/reel/XYZ/"


def test_descripcion_y_repost_dejan_solo_lo_importante():
    assert alt_util("Photo by Daniela on August 1, 2022") == ""
    assert "hija" in alt_util("Graduación con mi hija en la universidad").lower()
    assert es_repost("Daniela reposteó una publicación")
    info = incorporar_datos_importantes({"nombre": "Daniela Álvarez"}, [{
        "tipo": "compartida",
        "texto": ("Reposteó. Con mi hija celebramos su grado en la Universidad EAFIT. "
                  "Trabajo como analista en Global Seguros. Tengo 34 años."),
    }])
    assert "hija" in info["familia"].lower()
    assert "Universidad EAFIT" in info["educacion"]
    assert "analista" in info["experiencia"].lower()
    assert info["edad"] == "Tengo 34 años"
    assert "Reposteó" not in " ".join(info.values())


def test_un_comentario_no_se_guarda_como_hecho_y_el_logro_si():
    articulo = "\n".join([
        "Feliz de haber logrado mi maestría.",
        "Ver todos los comentarios",
        "maria",
        "Mi hijo empieza el colegio",
    ])
    texto = caption_de_publicacion("", articulo)
    assert "maestría" in texto
    assert "hijo" not in texto.lower()
    info = incorporar_datos_importantes({"nombre": "Ana"}, [
        {"tipo": "publicacion", "texto": texto},
        {"tipo": "compartida", "texto": "Con mi hija celebramos su grado en la Universidad EAFIT."},
    ])
    assert "hijo" not in (info.get("familia") or "").lower()
    assert "hija" in info["familia"].lower()
    assert "maestr" in info["logros"].lower()
    assert "colegio" not in (info.get("educacion") or "").lower()


def test_el_repost_del_catalogo_no_se_queda_fuera():
    from instagram_activity_scraper import InstagramActivityScraper
    with tempfile.TemporaryDirectory() as tmp:
        bot = InstagramActivityScraper(cookie_file=str(Path(tmp) / "c.json"),
                                       profile_dir=str(Path(tmp) / "p"))
        posts = [{"tipo": "publicacion", "texto": f"Caption propio número {i} sin tema de catálogo."} for i in range(3)]
        posts.append({"tipo": "compartida", "texto": "Mira este paisaje de la tarde en el parque con amigos."})
        posts.append({"tipo": "compartida", "texto": "Mi hija entra a la universidad este año y estamos muy felices."})
        elegidas = bot._elegir(posts, 1)
        assert sum(1 for p in elegidas if p["tipo"] == "publicacion") == 1
        assert any("universidad" in p["texto"] for p in elegidas)


def test_la_publicacion_pesa_igual_que_una_propia():
    from instagram_activity_scraper import InstagramActivityScraper
    with tempfile.TemporaryDirectory() as tmp:
        bot = InstagramActivityScraper(cookie_file=str(Path(tmp) / "c.json"),
                                       profile_dir=str(Path(tmp) / "p"))
        assert bot.analisis.peso_compartida == bot.analisis.peso_propia
        assert bot.analisis.prefijo_archivos == "instagram"


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
