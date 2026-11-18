"""Trabajo, estudios, cursos, experiencia, mensajes y publicaciones no se mezclan.

Ejecutar:  python -m tests.test_tipo_dato
"""
from app.contenido import describir_publicacion, excluidas_de_ficha
from app.ingesta_actividad import hechos_desde_info
from app.perfil_redes import aplicar_lo_publicado, categorias_oracion, hechos_desde_ficha
from app.tipo_dato import clasificar, eje_ficha, tipo_contenido


def test_trabajo_estudios_cursos_y_experiencia_no_se_pisan():
    assert eje_ficha("Trabajo como analista en Global Seguros") == "Trabajo"
    assert eje_ficha("Estudié ingeniería en la Universidad EAFIT") == "Estudios"
    assert eje_ficha("Hice un curso de Excel en Platzi") == "Cursos"
    assert eje_ficha("Completé la certificación AWS") == "Cursos"
    assert eje_ficha("Trabajé como analista en Bancolombia de 2018 a 2022") == "Experiencia"
    assert eje_ficha("Analista en Sura (2019 - 2023)") == "Experiencia"
    assert eje_ficha("Docente en la Universidad EAFIT") == "Trabajo"
    assert "Trabajo" not in categorias_oracion("Estudié ingeniería en la Universidad EAFIT.")
    assert categorias_oracion("Estudié ingeniería en la Universidad EAFIT.") == ["Estudios"]


def test_mensaje_no_es_publicacion_ni_ficha():
    assert tipo_contenido("comentario") == "Mensaje"
    assert tipo_contenido("mensaje") == "Mensaje"
    assert tipo_contenido("compartida") == "Publicacion"
    assert tipo_contenido("restack") == "Publicacion"
    assert clasificar("Feliz viernes", origen="comentario") == "Mensaje"
    assert clasificar("Feliz viernes", origen="publicacion") == "Publicacion"
    d = describir_publicacion({"texto": "Qué buen post", "tipo": "comentario"})
    assert "mensaje" in d["resumen"].lower()
    info = aplicar_lo_publicado(
        {"experiencia": "Autónomo", "educacion": "Universidad de Pamplona"},
        [{"tipo": "comentario", "texto": "Trabajo como gerente en otra empresa."}],
    )
    assert info["experiencia"] == "Autónomo"
    assert "gerente" not in info["experiencia"]


def test_descripcion_e_informacion_no_son_trabajo():
    assert eje_ficha("Amante del ciclismo y el café en Medellín", seccion="Descripcion") == "Descripcion"
    assert eje_ficha("Dato del perfil sin cargo", seccion="Informacion") == "Informacion"
    hechos = hechos_desde_info({
        "titular": "Analista",
        "bio": "Escribo sobre finanzas familiares",
        "experiencia": "Analista en Global. Trabajé en Bancolombia (2018 - 2022)",
        "educacion": "Universidad EAFIT. Curso de Excel en Platzi",
        "informacion": "Perfil público desde 2019",
    }, incluir_red=False)
    por = {}
    for h in hechos:
        por.setdefault(h["categoria"], []).append(h["contenido"])
    assert por["Situacion actual"] == ["Analista"]
    assert any("finanzas" in t.lower() for t in por["Descripcion"])
    assert any("Global" in t for t in por["Trabajo"])
    assert any("Bancolombia" in t for t in por.get("Experiencia", []))
    assert any("EAFIT" in t for t in por["Estudios"])
    assert any("Platzi" in t for t in por.get("Cursos", []))
    assert "Platzi" not in " ".join(por["Estudios"])
    assert por["Informacion"] == ["Perfil público desde 2019"]


def test_curso_en_publicacion_propia_si_dice_lo_hizo():
    info = aplicar_lo_publicado({}, [
        {"tipo": "publicacion", "texto": "Hice un curso de Python en Platzi."},
    ])
    assert "Platzi" in (info.get("cursos") or "")
    assert not info.get("educacion")
    suelta = aplicar_lo_publicado({}, [
        {"tipo": "publicacion", "texto": "Vi un anuncio de un curso de Python en Platzi."},
    ])
    assert not suelta.get("cursos")
    assert not suelta.get("educacion")


def test_empleo_pasado_de_ficha_es_experiencia():
    hechos = hechos_desde_ficha({"people": [{
        "full_name": "Ana Gómez",
        "headline": "Analista actual",
        "description": "Me apasiona el dato.",
        "employment_history": [
            {"title": "Analista", "organization_name": "Global Seguros"},
            {"title": "Practicante", "organization_name": "Sura",
             "start_date": "2018", "end_date": "2019"},
        ],
        "educations": [{"degree": "Diplomado en seguros", "school_name": "Platzi"}],
    }]})
    por = {h["categoria"]: h["contenido"] for h in hechos}
    assert "Global" in por["Trabajo"]
    assert "Sura" in por["Experiencia"]
    assert "Analista actual" in por["Situacion actual"]
    assert "apasiona" in por["Descripcion"].lower()
    assert por.get("Cursos") and "Platzi" in por["Cursos"]


def test_contenido_no_entra_a_la_ficha():
    assert "Mensaje" in excluidas_de_ficha()
    assert "Publicacion" in excluidas_de_ficha()
    assert "Comentario" in excluidas_de_ficha()


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
