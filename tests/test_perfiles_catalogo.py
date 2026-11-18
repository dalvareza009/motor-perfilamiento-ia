"""Perfiles de cliente del catálogo Global 2026."""
from app.perfiles_catalogo import PERFILES, fragmentos, sugerencias
from app.perfil_redes import sugerir_productos


def test_hay_cinco_lineas_del_catalogo_2026():
    ids = [p["id"] for p in PERFILES]
    assert ids == [
        "educativo-garantizada", "educativo-profesional-segura",
        "vida", "pensiones", "rentas-flex",
    ]
    filas = fragmentos()
    assert any(f["categoria"] == "perfil de cliente" and f["producto"] == "Seguro educativo"
               for f in filas)
    assert any(f["categoria"] == "dato interno de cartera" and "SMMLV" in f["contenido"]
               for f in filas)
    assert all("salario" not in f["contenido"].lower() or f["categoria"] == "dato interno de cartera"
               for f in filas if f["categoria"] == "perfil de cliente")


def test_hijos_y_edad_31_50_encajan_con_educativo():
    pares = sugerencias([
        {"categoria": "Hijos", "contenido": "Tiene hijos (dato declarado por la persona). bio: «Mamá de Valentina»"},
        {"categoria": "Edad", "contenido": "38 años"},
        {"categoria": "Ubicacion", "contenido": "Vive en Bogotá"},
        {"categoria": "Estado civil", "contenido": "Casada"},
    ])
    productos = {p for p, _ in pares}
    assert "Seguro educativo" in productos
    assert any("hijo" in r.lower() for p, r in pares if p == "Seguro educativo")
    hechos = [
        {"categoria": "Hijos", "contenido": "Tiene hijos (dato declarado por la persona)."},
        {"categoria": "Edad", "contenido": "38 años"},
        {"categoria": "Ubicacion", "contenido": "Bogotá"},
    ]
    titulos = {s["titulo"] for s in sugerir_productos(hechos)}
    assert "Seguro educativo" in titulos
    edu = next(s for s in sugerir_productos(hechos) if s["titulo"] == "Seguro educativo")
    assert "Catálogo 2026" in edu["contenido"]


def test_soltero_joven_encaja_con_vida_no_con_educativo():
    pares = sugerencias([
        {"categoria": "Estado civil", "contenido": "Soltero"},
        {"categoria": "Edad", "contenido": "28 años"},
        {"categoria": "Ubicacion", "contenido": "Medellín"},
    ])
    productos = {p for p, _ in pares}
    assert "Seguro de vida" in productos
    assert "Seguro educativo" not in productos


def test_mayor_de_50_encaja_con_pension_y_rentas():
    pares = sugerencias([
        {"categoria": "Edad", "contenido": "58 años"},
        {"categoria": "Ubicacion", "contenido": "Manizales"},
    ])
    productos = {p for p, _ in pares}
    assert any(p.startswith("Seguro de pensi") for p in productos)
    assert "Seguro renta vitalicia" in productos
    assert "Seguro educativo" not in productos


def test_sin_hechos_no_inventa_producto():
    assert sugerencias([]) == []
    assert sugerencias([{"categoria": "Descripcion", "contenido": "Amante del ciclismo"}]) == []


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
