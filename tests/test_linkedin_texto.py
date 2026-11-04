"""Pruebas de la capa de LinkedIn (sin navegador ni base de datos).

Ejecutar:  python -m tests.test_linkedin_texto
"""
from app.linkedin_texto import (evaluar_publicacion, extraer_publicaciones, intereses_de_texto,
                                motivo_sensible, pagina_es_muro, persona_de_url, personas_linkedin)

PERFIL = "https://www.linkedin.com/in/ana-gomez"
HTML_PUBLICO = """
<html><body>
  <article data-urn="urn:li:activity:100">
    <time datetime="2026-03-01">1 mes</time>
    <span>Terminé la maestría en la universidad y sigo estudiando.</span>
  </article>
  <div data-urn="urn:li:activity:200">
    <span>El domingo salí en moto con el grupo de ciclismo del trabajo.</span>
  </div>
  <div data-urn="urn:li:member:5"><span>Este bloque es el perfil, no una publicación.</span></div>
</body></html>
"""
HTML_MURO = """
<html><body>
  <div class="authwall">
    <h1>Sign in to view Ana's full profile</h1>
    <p>Join LinkedIn to see this profile.</p>
  </div>
</body></html>
"""
AUTORIZADOS = [{
    "nombre": "Ana Gómez",
    "clave_cliente": "CL0001",
    "autorizado": True,
    "autorizacion": "Autorización escrita del 1 de marzo para leer el perfil público.",
    "urls": [PERFIL],
}]


def test_muro_de_acceso_no_trae_publicaciones():
    assert pagina_es_muro(HTML_MURO)
    assert extraer_publicaciones(HTML_MURO) == []
    assert pagina_es_muro("<html></html>", "https://www.linkedin.com/login")


def test_extrae_publicaciones_por_urn_y_deja_el_perfil():
    posts = extraer_publicaciones(HTML_PUBLICO)
    assert [p["urn"] for p in posts] == ["urn:li:activity:100", "urn:li:activity:200"]
    assert posts[0]["tiempo"] == "2026-03-01"
    assert "maestría" in posts[0]["texto"]


def test_politica_y_religion_se_omiten_pero_el_salario_cuenta():
    politica = "Invita a la campaña electoral de su partido político y pide el voto para las elecciones."
    religion = "Cuenta que todos los domingos va a la iglesia y lee la biblia con su comunidad."
    for texto, motivo in ((politica, "politica"), (religion, "religion")):
        assert motivo_sensible(texto) == motivo
        evaluacion = evaluar_publicacion(texto)
        assert evaluacion["omitida"] and evaluacion["intereses"] == []
    # El salario NO es restrictivo: se conserva como señal de ingresos.
    salario = "En la publicación detalla su salario mensual y el sueldo del cargo actual en la empresa."
    assert motivo_sensible(salario) == ""
    evaluacion = evaluar_publicacion(salario)
    assert not evaluacion["omitida"] and evaluacion["salario"]


def test_casado_propone_seguro_de_vida():
    familia = intereses_de_texto("En su perfil indica que es casado y comparte su vida con su pareja.")
    assert any(i["producto"] == "Seguro de vida" and i["tema"] == "familia" for i in familia)


def test_estudios_y_moto_proponen_producto_y_razon():
    estudios = intereses_de_texto("Terminé la maestría en la universidad y sigo estudiando este año.")
    assert any(i["producto"] == "Seguro educativo" and i["tema"] == "estudios" for i in estudios)
    moto = intereses_de_texto("El domingo salí en moto con el grupo de ciclismo del trabajo y volvimos tarde.")
    assert any(i["producto"] == "Seguro de accidentes personales" for i in moto)


def test_sin_autorizacion_o_sin_perfil_publico_no_se_lee():
    personas, avisos = personas_linkedin(AUTORIZADOS)
    assert not avisos and persona_de_url(PERFIL, personas)["nombre"] == "Ana Gómez"
    assert persona_de_url(PERFIL + "/recent-activity/all/", personas) is None
    assert persona_de_url("https://www.linkedin.com/in/otra-persona", personas) is None
    ajenos, _ = personas_linkedin([{
        "nombre": "Otra", "autorizado": False, "autorizacion": "no aplica porque no autorizó",
        "urls": ["https://www.linkedin.com/in/otra"],
    }])
    assert ajenos == []


def test_un_texto_sin_tema_no_inventa_interes():
    assert intereses_de_texto("Hoy el clima en Medellín estuvo nublado durante toda la tarde de trabajo.") == []


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
