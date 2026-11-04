"""Pruebas de la validación (sin BD ni Ollama).  Ejecutar:  python -m tests.test_validacion"""
from app.validacion import validar

CLI = {"nombre": "Ana María Gómez", "edad": 34, "ciudad": "Medellín", "profesion": "Ingeniera",
       "universidad": "EAFIT", "producto_interes": "Seguro educativo"}
CON = "Producto orientado a apoyar la planificación financiera de la educación futura."


def test_cualquiera_de_los_tres_esloganes_vale_y_sin_eslogan_no():
    from app.validacion import ESLOGANES
    cli = {**CLI, "profesion": "Estudiante"}
    for eslogan in ESLOGANES:
        cuerpo = (f"Hola Ana, como estudiante, en Global Seguros protegemos tu educación. "
                  f"¿Conversamos con un asesor? {eslogan}.")
        assert validar(cuerpo, "", "whatsapp", cli, CON) == [], eslogan
    sin = validar("Hola Ana, en Global Seguros protegemos tu educación. ¿Conversamos?",
                  "", "whatsapp", cli, CON)
    assert any("eslógan" in x or "eslogan" in x for x in sin)


def test_los_limites_subieron_para_explicar_el_seguro():
    from app.validacion import LIMITE_PALABRAS
    assert LIMITE_PALABRAS["whatsapp"] == 70 and LIMITE_PALABRAS["correo"] == 130


def test_mensaje_correcto():
    cuerpo = ("Hola Ana, en Global Seguros el Seguro educativo apoya la planificación financiera "
              "de la educación futura. ¿Conversamos con un asesor? Tu tranquilidad, en un solo lugar.")
    assert validar(cuerpo, "", "whatsapp", CLI, CON) == []


def test_detecta_prohibidos_y_supuestos():
    cuerpo = "Hola Ana, por tus hijos te damos un descuento del 20% en tu salario."
    e = " ".join(validar(cuerpo, "", "whatsapp", CLI, CON))
    assert "hijo" in e and "descuento" in e and "salario" in e and "'20'" in e


def test_supuesto_permitido_si_esta_en_los_datos():
    cli = {**CLI, "profesion": "Estudiante"}
    cuerpo = "Hola Ana, como estudiante puedes ver el Seguro educativo."
    assert not any("estudiante" in x for x in validar(cuerpo, "", "whatsapp", cli, CON))


def test_nombre_asunto_y_largo():
    assert any("nombre" in x for x in validar("Hola, conversemos sobre el seguro.", "", "whatsapp", CLI, CON))
    assert any("asunto" in x.lower() for x in validar("Hola Ana, conversemos.", "", "correo", CLI, CON))
    largo = "Hola Ana " + "palabra " * 90
    assert any("palabras" in x for x in validar(largo, "", "whatsapp", CLI, CON))


def test_marcadores_sin_reemplazar():
    assert any("marcadores" in x for x in validar("Hola Ana, {nombre} mira esto.", "", "whatsapp", CLI, CON))


def test_nombre_de_producto_y_100_por_ciento_si_estan_en_el_conocimiento():
    con = "GlobalUniversidad Garantizada: Garantizado – 100% pago valor de la matrícula."
    ok = ("Hola Ana, GlobalUniversidad Garantizada de Global Seguros cubre el 100% de la matrícula. "
          "¿Conversamos? Siempre a tu lado en todos los momentos de la vida.")
    assert validar(ok, "", "whatsapp", CLI, con) == []
    # sin respaldo en el conocimiento, sí se rechaza
    assert any("promesa" in x for x in validar(ok, "", "whatsapp", CLI, CON))


def test_otras_promesas_siempre_se_rechazan():
    con = "Global Seguros no maneja descuentos."          # que el producto hable de 'descuentos' no los habilita
    e = validar("Hola Ana, tienes un descuento especial.", "", "whatsapp", CLI, con)
    assert any("descuento" in x for x in e)


def test_hijos_no_se_asume_aunque_el_producto_hable_de_hijos():
    con = "Protege la educación de tus hijos con una solución pensada para planear su futuro."
    e = validar("Hola Ana, protege la educación de tus hijos.", "", "whatsapp", CLI, con)
    assert any("hijo" in x for x in e)


def test_exige_marca_invitacion_y_nada_de_datos_invasivos():
    sin_marca = validar("Hola Ana, ¿conversamos sobre el seguro?", "", "whatsapp", CLI, CON)
    assert any("Global Seguros" in x for x in sin_marca)
    sin_cierre = validar("Hola Ana, en Global Seguros tenemos el Seguro educativo.", "", "whatsapp", CLI, CON)
    assert any("conversar" in x for x in sin_cierre)
    # Nombrar la universidad concreta suena invasivo aunque el dato exista.
    invasivo = validar("Hola Ana, como estudiante en EAFIT, en Global Seguros ¿conversamos?",
                       "", "whatsapp", CLI, CON)
    assert any("invasivo" in x for x in invasivo)
    # La condición general sí está permitida.
    general = ("Hola Ana, como estudiante, en Global Seguros podemos proteger tu educación. "
               "¿Conversamos con un asesor? Pensar en grande, es pensar con Global Seguros.")
    cli = {**CLI, "profesion": "Estudiante"}
    assert validar(general, "", "whatsapp", cli, CON) == []


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)