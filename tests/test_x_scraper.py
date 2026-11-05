"""Pruebas de la ficha de X, sin navegador.

Ejecutar:  python -m tests.test_x_scraper
"""
import tempfile
from pathlib import Path

from app.ingesta_actividad import hechos_desde_info
from app.mensajes_prueba import _cliente
from app.perfil_redes import clasificar_url, sugerir_productos
from x_activity_scraper import (XActivityScraper, armar_publicacion, es_cuenta_protegida,
                                es_logro, incorporar_datos_importantes, parsear_ficha_x,
                                resumir_interacciones, url_de_publicacion, url_pide_login)


FICHA = {
    "nombre": "Daniela Álvarez\n@dani",
    "bio": "\n".join([
        "Mamá de una hija",
        "Analista en Global Seguros",
        "Universidad EAFIT",
        "Me gradué con premio",
        "Vive en Medellín",
        "(2026-09-01 - None)",
        "Seguir",
    ]),
    "ubicacion": "Medellín",
    "unio": "Se unió en marzo de 2020",
    "seguidores": "1.543 Seguidores",
    "cuerpo": "Daniela Álvarez\n1.543 Seguidores",
}


def test_la_ficha_separa_persona_logro_y_quita_fechas():
    info = parsear_ficha_x(FICHA)
    assert info["nombre"] == "Daniela Álvarez"
    assert info["seguidores"] == "1.543"
    assert "hija" in info["familia"].lower()
    assert "analista" in info["experiencia"].lower()
    assert "Universidad EAFIT" in info["educacion"]
    assert "Medellín" in info["ubicacion"]
    assert "gradu" in info["logros"].lower()
    assert "marzo de 2020" in info["en_x_desde"]
    assert "2026-09-01" not in info["acerca"]
    assert "None" not in info["acerca"]
    assert "Seguir" not in info["acerca"]
    hechos = hechos_desde_info(info)
    categorias = {h["categoria"] for h in hechos}
    assert "Logros" in categorias
    assert "Descripcion" in categorias
    assert "analista" in (info.get("bio") or "").lower()
    productos = {p["titulo"] for p in sugerir_productos(hechos)}
    assert "Seguro de vida" in productos
    assert "Seguro educativo" in productos


def test_cuenta_protegida_no_se_confunde_con_un_perfil_visible():
    assert es_cuenta_protegida("Estas publicaciones están protegidas")
    info = parsear_ficha_x({"nombre": "Ana", "bio": "Mamá de una hija", "protegida": True,
                            "cuerpo": "Estas publicaciones están protegidas"})
    assert info["privado"] is True
    assert "hija" in info["familia"].lower()


def test_la_pantalla_de_acceso_no_se_confunde_con_un_perfil():
    assert url_pide_login("https://x.com/i/flow/login")
    assert url_pide_login("https://x.com/account/access")
    assert not url_pide_login("https://x.com/home")
    assert not url_pide_login("https://x.com/dani")


def test_la_url_de_un_post_queda_limpia_y_el_perfil_se_acepta():
    assert url_de_publicacion("https://x.com/dani/status/123?s=20") == "https://x.com/dani/status/123"
    assert url_de_publicacion("https://twitter.com/dani/status/99") == "https://x.com/dani/status/99"
    assert url_de_publicacion("https://x.com/i/status/1") == ""
    assert clasificar_url("https://twitter.com/dani")[1] == "https://x.com/dani"
    assert clasificar_url("https://x.com/dani/status/123") is None


def test_publicacion_respuesta_y_logro_no_guardan_fecha_iso():
    post = armar_publicacion({
        "texto": "Con mi hija celebramos el grado. (2026-09-01T00:00:00Z)",
        "datetime": "2026-09-01T00:00:00.000Z",
        "etiqueta": "",
        "href": "https://x.com/dani/status/55",
        "respuesta": True,
        "respuestas": "4 Respuestas",
        "reposts": "1 Republicar",
        "me_gusta": "12 Me gusta",
    }, "https://x.com/dani", "Daniela")
    assert post["tipo"] == "respuesta"
    assert "2026-09-01" not in post["texto"]
    assert post["tiempo"] == "1 de septiembre de 2026"
    assert "T00:00:00" not in post["tiempo"]
    logro = armar_publicacion({
        "texto": "Me nombraron analista después de la maestría.",
        "href": "https://x.com/dani/status/77",
        "social": "",
    }, "https://x.com/dani", tipo_forzado="logro")
    assert logro["tipo"] == "logro"
    assert es_logro(logro["texto"])
    repost = armar_publicacion({
        "texto": "Un texto bastante largo de otra persona sobre su familia y su trabajo.",
        "social": "Daniela Álvarez reposteó",
        "href": "https://x.com/dani/status/88",
    }, "https://x.com/dani")
    assert repost["tipo"] == "compartida"


def test_de_las_publicaciones_salen_logros_e_interacciones():
    info = incorporar_datos_importantes({"nombre": "Daniela Álvarez"}, [{
        "tipo": "respuesta",
        "texto": "Con mi hija celebramos su grado en la Universidad EAFIT. Tengo 34 años. Me gradué con premio.",
    }])
    assert "hija" in info["familia"].lower()
    assert "Universidad EAFIT" not in (info.get("educacion") or "")
    assert info["edad"] == "Tengo 34 años"
    assert "premio" not in (info.get("logros") or "").lower()
    resumen = resumir_interacciones([
        {"tipo": "respuesta", "respuestas_n": "3 respuestas", "reposts_n": "1", "me_gusta": "10 Me gusta"},
        {"tipo": "compartida", "respuestas_n": "99", "reposts_n": "99", "me_gusta": "99"},
        {"tipo": "publicacion", "respuestas_n": "2 respuestas", "reposts_n": "4 republicaciones", "me_gusta": "1.234 Me gusta"},
    ])
    assert "1 respuestas propias" in resumen
    assert "1 republicaciones leídas" in resumen
    assert "1.244" not in resumen
    assert "5 respuestas" in resumen
    assert "1.244 me gusta" in resumen or "1244 me gusta" in resumen
    hechos = hechos_desde_info({**info, "interacciones": resumen})
    cliente = _cliente("Daniela Álvarez", "Seguro de vida", hechos)
    assert "hija" not in (cliente.get("profesion") or "").lower()
    assert "Medellín" not in (cliente.get("profesion") or "")
    assert any(h["categoria"] == "Interacciones" for h in hechos)


def test_el_repost_del_catalogo_entra_y_no_se_copia_como_dato_personal():
    with tempfile.TemporaryDirectory() as tmp:
        bot = XActivityScraper(cookie_file=str(Path(tmp) / "c.json"),
                               profile_dir=str(Path(tmp) / "p"))
        posts = [{"tipo": "publicacion", "texto": f"Nota propia {i} sin un tema del catalogo de seguros."} for i in range(3)]
        posts.append({"tipo": "compartida", "texto": "Mira este paisaje de la tarde en el parque con amigos."})
        posts.append({"tipo": "compartida", "texto": "Mi hija entra a la universidad este año y estamos muy felices."})
        una = bot._elegir(posts, 1)
        assert len(una) == 1
        assert "universidad" in una[0]["texto"]
        dos = bot._elegir(posts, 2)
        assert len(dos) == 2
        assert any("universidad" in p["texto"] for p in dos)
    info = incorporar_datos_importantes({"nombre": "Daniela Álvarez"}, [
        {"tipo": "compartida", "texto": "Mi hija entra a la universidad este año y estamos muy felices."},
        {"tipo": "publicacion", "texto": "Me gradué con premio en la maestría."},
    ])
    assert not info.get("familia")
    assert "premio" not in (info.get("logros") or "").lower()
    assert "maestr" in (info.get("educacion") or info.get("estado_academico") or "").lower()


def test_se_reservan_cupos_para_respuestas_y_logros():
    with tempfile.TemporaryDirectory() as tmp:
        bot = XActivityScraper(cookie_file=str(Path(tmp) / "c.json"),
                               profile_dir=str(Path(tmp) / "p"))
        assert bot.analisis.peso_compartida == bot.analisis.peso_propia
        posts = [{"tipo": "publicacion", "texto": f"p{i}"} for i in range(4)]
        posts += [{"tipo": "respuesta", "texto": "r1"}, {"tipo": "logro", "texto": "l1"}]
        elegidas = bot._elegir(posts, 2)
        assert len(elegidas) == 2
        tipos = {p["tipo"] for p in elegidas}
        assert "publicacion" in tipos
        assert tipos & {"respuesta", "logro"}
        muchas = [{"tipo": "publicacion", "texto": f"p{i}"} for i in range(8)]
        muchas += [{"tipo": "respuesta", "texto": f"r{i}"} for i in range(8)]
        assert len(bot._elegir(muchas, 4)) == 4


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
