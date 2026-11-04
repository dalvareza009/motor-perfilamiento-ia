"""Pruebas del prompt de mensajes (sin BD ni Ollama).

Ejecutar:  python -m tests.test_mensajes_prompt
"""
from app.mensajes import ESLOGANES, _prompt, condicion_general

CLIENTE = {
    "nombre": "Juan Manuel López", "ciudad": "Medellín", "profesion": "Estudiante",
    "universidad": "Systems Engineering Student At EAFIT University",
    "producto_interes": "Seguro Educativo",
    "hechos_perfil": "- Estudios: Systems Engineering student at EAFIT University",
}


def test_la_condicion_es_general_y_sin_instituciones():
    assert condicion_general(CLIENTE) == "estudiante"
    trabajador = {**CLIENTE, "profesion": "Analista de datos en Global Seguros",
                  "hechos_perfil": "Trabajo: Analista de datos en Global Seguros"}
    assert condicion_general(trabajador) == "persona que trabaja"


def test_el_prompt_no_filtra_datos_concretos():
    eslogan = ESLOGANES[0]
    p = _prompt(CLIENTE, "Información del producto.", "whatsapp", [], eslogan)
    assert "EAFIT" not in p and "Eafit" not in p          # la universidad NO llega al modelo
    assert "Medellín" not in p                             # ni la ciudad
    assert "estudiante" in p                               # solo la condición general
    assert "Global Seguros" in p and eslogan in p          # marca + eslogan elegido
    assert "conversar" in p                                # invitación a conversar
    assert "invasivo" in p                                 # regla de privacidad explícita
    assert "50 y 70 palabras" in p and "explicación MUY resumida" in p  # más largo y explica


def test_cada_eslogan_puede_salir_en_el_prompt():
    for eslogan in ESLOGANES:
        assert eslogan in _prompt(CLIENTE, "Info.", "whatsapp", [], eslogan)


def test_el_prompt_de_correo_tambien_pide_marca_y_cierre():
    p = _prompt(CLIENTE, "Información del producto.", "correo", [], ESLOGANES[1])
    assert ESLOGANES[1] in p and "conversar" in p and "EAFIT" not in p
    assert "90 y 130 palabras" in p


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
