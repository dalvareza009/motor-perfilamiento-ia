"""Pruebas de actividad -> recomendaciones del scraper (sin navegador).

Ejecutar:  python -m tests.test_linkedin_scraper_recomendaciones
"""
import csv
import json
import tempfile
from pathlib import Path

from linkedin_activity_scraper import LinkedInActivityScraper

PERFIL = "https://www.linkedin.com/in/ana-gomez/"


def _post(urn, texto, tiempo="1 sem"):
    return {
        "perfil": PERFIL, "urn": urn,
        "url_publicacion": LinkedInActivityScraper.url_desde_urn(urn),
        "tipo": "publicacion", "autor": "Ana Gómez", "texto": texto,
        "tiempo": tiempo, "hashtags": "", "enlaces": "", "reacciones": "",
        "comentarios": "", "fecha_extraccion": "2026-10-29 23:40:00",
    }


PUBLICACIONES = [
    _post("urn:li:activity:1",
          "Terminé la maestría en la universidad y sigo estudiando un posgrado este año."),
    _post("urn:li:activity:2",
          "Este fin de semana salí en moto con el grupo de ciclismo y recorrimos la montaña."),
    _post("urn:li:activity:3",
          "Con mi hija y mi familia celebramos su primer año de colegio en la ciudad."),
    _post("urn:li:activity:4",
          "Después de pensar en mi jubilación y la pensión, empecé un plan de ahorro e inversión."),
    _post("urn:li:activity:5",
          "En el trabajo me subieron el salario y el sueldo quedó publicado en la oferta interna."),
    _post("urn:li:activity:6",
          "Hoy el clima estuvo nublado durante toda la tarde y no pasó nada especial en la oficina."),
]


def _bot(tmp):
    return LinkedInActivityScraper(cookie_file=str(Path(tmp) / "cookies.json"),
                                   profile_dir=str(Path(tmp) / "perfil"))


def test_recomendaciones_salen_de_la_actividad_y_se_ordenan():
    with tempfile.TemporaryDirectory() as tmp:
        bot = _bot(tmp)
        bot.analizar_publicaciones(PUBLICACIONES)
        por_producto = {r["producto"]: r for r in bot.recomendaciones}
        # Estudios + hija/colegio apoyan el educativo en 2 publicaciones distintas.
        assert por_producto["Seguro educativo"]["publicaciones_que_apoyan"] == 2
        assert por_producto["Seguro educativo"]["puntuacion"] >= 6  # 2 propias con tema pesan 3+3
        assert "Seguro de vida" in por_producto
        assert "Seguro de accidentes personales" in por_producto
        assert "Seguro de pensión" in por_producto and "Seguro renta voluntaria" in por_producto
        assert bot.recomendaciones[0]["producto"] == "Seguro educativo"


def test_lo_sensible_se_omite_y_no_queda_en_ningun_lado():
    with tempfile.TemporaryDirectory() as tmp:
        bot = _bot(tmp)
        bot.analizar_publicaciones(PUBLICACIONES + [
            _post("urn:li:activity:90",
                  "Invita a la campaña electoral de su partido político y pide el voto en elecciones.")])
        # Política sigue restringida y se omite; el salario ya no.
        assert bot.omitidas_sensibles["politica"] == 1
        assert not dict(bot.omitidas_sensibles).get("salario")
        # La publicación de salario SÍ se conserva y suma el tema ingresos.
        post_salario = next(p for p in bot.resultados if "salario" in p["texto"])
        assert "tema:ingresos" in post_salario["motivos_relevancia"]
        assert bot.resumen[PERFIL]["temas_detectados"]["ingresos"] == 1
        assert bot.resumen[PERFIL]["publicaciones_extraidas"] == 7
        assert bot.resumen[PERFIL]["omitidas_sensibles"] == 1


def test_los_tres_archivos_se_cruzan_por_evidencia():
    with tempfile.TemporaryDirectory() as tmp:
        bot = _bot(tmp)
        bot.analizar_publicaciones(PUBLICACIONES)
        cwd = Path.cwd()
        import os
        os.chdir(tmp)
        try:
            archivos = bot.guardar_resultados()
        finally:
            os.chdir(cwd)
        with open(Path(tmp) / archivos["recomendaciones"], encoding="utf-8-sig") as f:
            filas = list(csv.DictReader(f))
        educativo = next(r for r in filas if r["producto"] == "Seguro educativo")
        assert educativo["publicaciones_que_apoyan"] == "2"
        assert "maestría" in educativo["evidencias"]
        assert "feed/update/urn:li:activity:1" in educativo["urls_publicaciones"]
        resumen = json.loads((Path(tmp) / archivos["resumen"]).read_text(encoding="utf-8"))
        assert resumen["perfiles"][PERFIL]["temas_detectados"]["estudios"] == 2
        assert resumen["omitidas_por_tema_sensible"] == {}


def test_url_solo_para_publicaciones_enlazables():
    assert LinkedInActivityScraper.url_desde_urn("urn:li:ugcPost:9").endswith("urn:li:ugcPost:9/")
    assert LinkedInActivityScraper.url_desde_urn("urn:li:member:5") == ""


def test_modo_web_espera_confirmacion_sin_teclado():
    # Desde el front no hay consola: «cancelar» debe bastar para salir de la espera.
    with tempfile.TemporaryDirectory() as tmp:
        bot = LinkedInActivityScraper(cookie_file=str(Path(tmp) / "c.json"),
                                      profile_dir=str(Path(tmp) / "p"),
                                      confirmar_login=lambda contexto="": "cancelar")
        bot.driver = object()
        assert bot.esperar_login_manual("prueba") is False


def test_cerrar_sin_preguntar_no_pide_enter():
    class Fake:
        def __init__(self): self.cerrado = False
        def get_cookies(self): return []
        def quit(self): self.cerrado = True

    with tempfile.TemporaryDirectory() as tmp:
        bot = _bot(tmp)
        bot.driver = Fake()
        bot.cerrar_navegador(preguntar=False)
        assert bot.driver is None


def test_fechas_y_ventana_de_un_ano():
    from datetime import date

    from linkedin_activity_scraper import parse_fecha_publicacion
    hoy = date(2026, 11, 2)
    assert parse_fecha_publicacion("21 de may.", hoy).isoformat() == "2026-05-21"
    assert parse_fecha_publicacion("10 de sept. de 2025", hoy).isoformat() == "2025-09-10"
    assert parse_fecha_publicacion("3 sem", hoy).isoformat() == "2026-10-12"
    assert parse_fecha_publicacion("14 de ene. de 2025", hoy).isoformat() == "2025-01-14"
    assert parse_fecha_publicacion("2026-09-01T00:00:00Z", hoy).isoformat() == "2026-09-01"
    with tempfile.TemporaryDirectory() as tmp:
        bot = _bot(tmp)
        posts = [
            _post("urn:li:activity:20", "Texto reciente propio con suficiente longitud para analizar bien.", "21 de may."),
            _post("urn:li:activity:21", "Texto antiguo que debe quedar fuera de la ventana anual completa.", "10 de sept. de 2025"),
        ]
        posts[0]["tipo"], posts[1]["tipo"] = "publicacion", "compartida"
        vigentes = bot.filtrar_y_ordenar(posts, hoy=hoy)
        assert [p["urn"] for p in vigentes] == ["urn:li:activity:20"]
        assert bot.ultimas_descartadas == 1


def test_propias_antes_que_compartidas_y_ficha_pesa_mas():
    with tempfile.TemporaryDirectory() as tmp:
        bot = _bot(tmp)
        bot.info_perfil[PERFIL] = {
            "perfil": PERFIL, "nombre": "Ana Gómez", "titular": "",
            "acerca": "Estudié en la universidad y ahora estoy haciendo una maestría con mucho esfuerzo.",
            "experiencia": "", "educacion": "", "ubicacion": ""}
        compartida = _post("urn:li:activity:30",
                           "Comparto que terminé la maestría en la universidad y sigo estudiando este año.")
        compartida["tipo"] = "compartida"
        bot.analizar_publicaciones([compartida])
        educativo = next(r for r in bot.recomendaciones if r["producto"] == "Seguro educativo")
        assert educativo["desde_el_perfil"]  # primero la ficha, luego las publicaciones
        assert compartida["relevancia"] == "media"  # compartida: señal más débil
        assert "compartida" in compartida["motivos_relevancia"]


def test_facebook_detecta_compartidas():
    from facebook_activity_scraper import es_compartida
    assert es_compartida("Ana Gómez compartió una publicación")
    assert not es_compartida("Ana Gómez")


def test_facebook_presentacion_queda_como_bio():
    from facebook_activity_scraper import parsear_ficha_facebook
    from app.ingesta_actividad import hechos_desde_info
    info = parsear_ficha_facebook("""
    Ana Gómez
    Presentación
    Amante del ciclismo y viajar con la familia
    Trabajo y educación
    Trabaja en Global Seguros
    """)
    assert "ciclismo" in (info.get("bio") or "").lower()
    assert "ciclismo" in " ".join(h["contenido"] for h in hechos_desde_info(info)).lower()


def test_facebook_ficha_separa_casado_estudios_y_trabajo():
    from facebook_activity_scraper import parsear_ficha_facebook
    cuerpo = """
    Buscar amigos
    Nueva notificación en la configuración
    Yimy Osvaldo Alvarez Gomez
    737 amigos
    Enviar mensaje
    Segovia · Autónomo liceo ignacio yepes yepes
    Universidad de Pamplona
    Todo
    Información
    Datos personales
    Vive en Segovia (Antioquia)
    De Remedios
    Casado Desde el 28 de febrero de 2003
    """
    info = parsear_ficha_facebook(cuerpo)
    assert "Segovia" in info["ubicacion"] and "Remedios" in info["ubicacion"]
    assert "casado" in info["estado_civil"].lower()
    assert "Universidad de Pamplona" in info["educacion"]
    assert "liceo" in info["experiencia"].lower()
    assert "Buscar amigos" not in info["acerca"]
    assert "clima" not in info["acerca"]


def test_facebook_solo_guarda_datos_personales():
    from datetime import date

    from facebook_activity_scraper import edad_de_texto, parsear_ficha_facebook, urls_about
    cuerpo = """
    Trabajo y educación
    Trabaja en Global Seguros
    Analista de datos en Global Seguros
    Estudió en Universidad EAFIT
    Información básica
    Fecha de nacimiento
    15 de marzo de 1990
    Casado
    Familia y relaciones
    Hermana · María Gómez
    Hija · Ana
    Hoy el clima estuvo nublado durante toda la tarde en la oficina
    """
    info = parsear_ficha_facebook(cuerpo, hoy=date(2026, 11, 3))
    assert info["edad"].endswith("36 años")
    assert "Global Seguros" in info["experiencia"]
    assert "Analista de datos" in info["experiencia"]
    assert "Universidad EAFIT" in info["educacion"]
    assert "Casado" in info["estado_civil"]
    assert "María Gómez" in info["familia"] and "Ana" in info["familia"]
    assert "clima" not in info["acerca"]
    assert edad_de_texto("Su hija tiene 8 años. Ella tiene 34 años.", date(2026, 11, 3)) == "34 años"
    assert urls_about("https://www.facebook.com/ana")[1].endswith("/about")
    assert "sk=about_family_and_relationships" in urls_about("https://www.facebook.com/profile.php?id=5")[-2]
    from facebook_activity_scraper import urls_likes_y_seguidos
    assert urls_likes_y_seguidos("https://www.facebook.com/ana")[1].endswith("/following")


def test_facebook_compartida_pesa_igual_que_propia_y_ficha_manda():
    # En Facebook compartir es publicar: mismo peso que la propia. Solo la
    # ficha del perfil sigue por encima.
    from facebook_activity_scraper import FacebookActivityScraper
    with tempfile.TemporaryDirectory() as tmp:
        cara = FacebookActivityScraper(cookie_file=str(Path(tmp) / "c.json"),
                                       profile_dir=str(Path(tmp) / "p"))
        compartida = _post("urn:li:activity:40",
                           "Comparto que terminé la maestría en la universidad y sigo estudiando.")
        compartida["tipo"] = "compartida"
        propia = _post("urn:li:activity:41",
                       "Terminé la maestría en la universidad y sigo estudiando este año también.")
        cara.analisis.analizar_publicaciones([compartida, propia])
        assert compartida["relevancia"] == propia["relevancia"] == "alta"
        edu = next(r for r in cara.analisis.recomendaciones if r["producto"] == "Seguro educativo")
        assert edu["puntuacion"] == cara.analisis.peso_propia * 2  # 3 + 3, no 3 + 1
        assert cara.analisis.peso_perfil > cara.analisis.peso_compartida


def test_guardar_resultados_sigue_siendo_opcional():
    """Los CSV quedan solo para depurar; el flujo web ya no los necesita."""
    with tempfile.TemporaryDirectory() as tmp:
        bot = _bot(tmp)
        bot.analizar_publicaciones(PUBLICACIONES)
        cwd = Path.cwd()
        import os
        os.chdir(tmp)
        try:
            archivos = bot.guardar_resultados()
        finally:
            os.chdir(cwd)
        assert "actividad" in archivos


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
