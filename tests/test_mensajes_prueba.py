"""Tres mensajes de prueba por prospecto, sin llamar al modelo ni a la base."""
from app import validacion
from app.mensajes_prueba import agrupar, redactar_tres, respaldo


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


def test_mensajes_salen_por_fecha_no_por_nombre():
    filas = [
        {"nombre": "Ana Gómez", "fuente_url": "u1", "red": "instagram", "producto": "P",
         "opcion": 1, "eslogan": "a", "cuerpo": "c1", "estado": "borrador",
         "errores_validacion": None, "creado_en": "2026-11-01T10:00:00"},
        {"nombre": "Carlos Pérez", "fuente_url": "u2", "red": "x", "producto": "P",
         "opcion": 1, "eslogan": "a", "cuerpo": "c2", "estado": "borrador",
         "errores_validacion": None, "creado_en": "2026-11-04T20:00:00"},
        {"nombre": "Carlos Pérez", "fuente_url": "u2", "red": "x", "producto": "P",
         "opcion": 2, "eslogan": "b", "cuerpo": "c3", "estado": "borrador",
         "errores_validacion": None, "creado_en": "2026-11-04T20:00:01"},
    ]
    grupos = agrupar(filas)
    assert [g["nombre"] for g in grupos] == ["Carlos Pérez", "Ana Gómez"]
    assert [o["opcion"] for o in grupos[0]["opciones"]] == [1, 2]


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
