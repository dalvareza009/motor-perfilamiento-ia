"""Preguntas sobre perfiles con scraping que no están en la lista de clientes."""
from app.asesor import reconocer_perfiles, sanear
from app.perfiles_consulta import armar_fichas, filtrar, texto


def _hechos():
    return [
        {"nombre": "Mariana Gutierrez Jaramillo", "red": "linkedin",
         "fuente_url": "https://www.linkedin.com/in/mariana-gutierrez-jaramillo/",
         "categoria": "Ubicacion", "titulo": "Ubicacion", "contenido": "Medellín, Colombia"},
        {"nombre": "Mariana Gutierrez Jaramillo", "red": "linkedin",
         "fuente_url": "https://www.linkedin.com/in/mariana-gutierrez-jaramillo/",
         "categoria": "Trabajo", "titulo": "Trabajo", "contenido": "Ingeniera de sistemas"},
        {"nombre": "Mariana Gutierrez Jaramillo", "red": "linkedin",
         "fuente_url": "https://www.linkedin.com/in/mariana-gutierrez-jaramillo/",
         "categoria": "Producto sugerido", "titulo": "Seguro de vida", "contenido": "Trabajo: Ingeniera"},
        {"nombre": "Jhonnathan Ocampo Diaz", "red": "linkedin",
         "fuente_url": "https://www.linkedin.com/in/jhonnathan-ocampo/",
         "categoria": "Estudios", "titulo": "Estudios", "contenido": "Estudiante de ingeniería"},
    ]


def test_la_ficha_solo_trae_lo_dicho():
    ficha = armar_fichas(_hechos())[1]
    assert ficha["nombre"] == "Mariana Gutierrez Jaramillo"
    assert ficha["ciudad"] == "Medellín"
    assert ficha["profesion"] == "Ingeniera de sistemas"
    assert ficha["producto_interes"] == "Seguro de vida"
    assert ficha["clave_cliente"] is None
    assert ficha["edad"] is None
    dicho = texto(ficha)
    assert "Medellín" in dicho
    assert "no está vinculado" in dicho
    assert "Edad" not in dicho


def test_filtra_por_ciudad_y_por_nombre():
    fichas = armar_fichas(_hechos())
    assert [f["nombre"] for f in filtrar(fichas, {"ciudad": "Medellín"})] == ["Mariana Gutierrez Jaramillo"]
    assert filtrar(fichas, {}, "Jhonnathan")[0]["universidad"] == "Estudiante de ingeniería"


def test_fuera_de_la_lista_no_se_descarta():
    crudo = sanear({
        "accion": "listar", "agrupar_por": None,
        "filtros": {"ciudad": "null"}, "canal": None, "nombre": None,
        "origen": "clientes", "no_soportado": ["estan por fuera de la lista"],
    })
    pedido = "que esten por fuera de la lista de clientes"
    listo = reconocer_perfiles(pedido, crudo)
    assert listo["origen"] == "perfiles"
    assert listo["filtros"] == {}
    assert listo["no_soportado"] == []


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
