"""Tres mensajes de prueba por prospecto, sin llamar al modelo ni a la base."""
from app import validacion
from app.mensajes_prueba import redactar_tres, respaldo


def test_el_respaldo_cumple_las_reglas():
    cuerpo = respaldo("Yimy Osvaldo Alvarez", "Seguro de vida",
                      "Tu tranquilidad, en un solo lugar")
    cliente = {"nombre": "Yimy Osvaldo Alvarez", "producto_interes": "Seguro de vida", "profesion": ""}
    assert validacion.validar(cuerpo, "", "whatsapp", cliente, "Seguro de vida") == []
    assert "casad" not in cuerpo.lower()
    assert "salario" not in cuerpo.lower()


def test_siempre_hay_tres_opciones_aunque_el_modelo_no_responda():
    opciones = redactar_tres("Ana Gómez", "Seguro educativo", [], generar=lambda *a, **k: None)
    assert len(opciones) == 3
    assert [o["opcion"] for o in opciones] == [1, 2, 3]
    esloganes = {o["eslogan"] for o in opciones}
    assert len(esloganes) == 3
    for op in opciones:
        assert "Ana" in op["cuerpo"]
        assert op["eslogan"] in op["cuerpo"]
        assert "Global Seguros" in op["cuerpo"]


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
