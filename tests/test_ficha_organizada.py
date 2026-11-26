"""La ficha solo trae datos de la persona, limpios y por apartados."""
from app.perfil_redes import limpiar_contenido_ficha, organizar_ficha


def test_quita_el_pie_y_los_perfiles_recomendados():
    sucio = ("Educación Universidad EAFIT Software engineering ene. de 2022 – jun. de 2026 "
             "Aptitudes: Microservices, Java y 11 aptitudes más Más perfiles para ti "
             "Mariana Gutierrez Security Developer Enviar mensaje Ana Sofia Rodriguez Orozco Systems Engineer")
    limpio = limpiar_contenido_ficha(sucio)
    assert limpio == "Universidad EAFIT Software engineering ene. de 2022 – jun. de 2026"
    assert limpiar_contenido_ficha(
        "Acerca de Accesibilidad Talent Solutions Pautas comunitarias "
        "LinkedIn Corporation © 2026 Centro de ayuda") == ""


def test_la_ficha_separa_estudios_y_no_trae_red_ni_contenido():
    hechos = [
        {"nombre": "Ana Prueba", "red": "linkedin", "categoria": "Estudios", "titulo": "Estudios",
         "contenido": "Universidad EAFIT"},
        {"nombre": "Ana Prueba", "red": "linkedin", "categoria": "Estudios", "titulo": "Estudios (2)",
         "contenido": "Universidad de Medellín"},
        {"nombre": "Ana Prueba", "red": "linkedin", "categoria": "Ubicacion", "titulo": "Ubicacion",
         "contenido": "Vive en Medellín. De Segovia (Antioquia)"},
        {"nombre": "Ana Prueba", "red": "linkedin", "categoria": "Seguidor", "titulo": "Seguidor",
         "contenido": "Sigue a Ana Prueba en esta red."},
        {"nombre": "Ana Prueba", "red": "linkedin", "categoria": "Publicacion", "titulo": "Publicacion",
         "contenido": "Publicó algo extenso sobre su trabajo y su familia reunida."},
        {"nombre": "Ana Prueba", "red": "instagram", "categoria": "Descripcion", "titulo": "Descripcion",
         "contenido": "ana.prueba 37 publicaciones 775 seguidores 186 seguidos"},
    ]
    ficha = organizar_ficha(hechos)
    por_clave = {s["clave"]: s for s in ficha}
    assert [i["texto"] for i in por_clave["estudios"]["items"]] == [
        "Universidad EAFIT", "Universidad de Medellín"]
    assert [i["texto"] for i in por_clave["lugar"]["items"]] == [
        "Vive en Medellín", "De Segovia (Antioquia)"]
    assert "presentacion" not in por_clave
    textos = " ".join(i["texto"] for s in ficha for i in s["items"])
    assert "Sigue a" not in textos
    assert "Publicó" not in textos


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
