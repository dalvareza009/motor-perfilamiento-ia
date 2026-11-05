"""Página de Facebook: URLs, likes/comentarios y cómo acercarse."""
from app.facebook_pagina import (acercamiento, clasificar_url_pagina, fusionar,
                                 url_perfil_facebook)


def test_acepta_url_de_pagina_facebook():
    assert clasificar_url_pagina("https://www.facebook.com/Mapfreco") == "https://www.facebook.com/Mapfreco"
    assert (clasificar_url_pagina("https://www.facebook.com/GlobalSegurosColombia")
            == "https://www.facebook.com/GlobalSegurosColombia")
    assert (clasificar_url_pagina("https://www.facebook.com/GlobalSegurosColombia/posts")
            == "https://www.facebook.com/GlobalSegurosColombia")
    assert (clasificar_url_pagina("https://www.facebook.com/pages/Global-Seguros/123456")
            == "https://www.facebook.com/Global-Seguros")
    assert (clasificar_url_pagina("https://www.facebook.com/profile.php?id=615512345")
            == "https://www.facebook.com/profile.php?id=615512345")
    assert clasificar_url_pagina("https://www.facebook.com/groups/123") is None
    assert clasificar_url_pagina("https://www.facebook.com/messages/t/1") is None
    assert clasificar_url_pagina("https://www.instagram.com/global/") is None


def test_limpia_url_de_quien_interactua():
    pagina = "https://www.facebook.com/GlobalSegurosColombia"
    assert (url_perfil_facebook("https://www.facebook.com/ana.perez?comment_id=1", pagina)
            == "https://www.facebook.com/ana.perez")
    assert (url_perfil_facebook("https://www.facebook.com/profile.php?id=1000123&comment_id=9", pagina)
            == "https://www.facebook.com/profile.php?id=1000123")
    assert (url_perfil_facebook("https://www.facebook.com/people/Ana-Perez/1000123", pagina)
            == "https://www.facebook.com/profile.php?id=1000123")
    assert url_perfil_facebook("https://www.facebook.com/GlobalSegurosColombia", pagina) is None
    assert url_perfil_facebook("https://www.facebook.com/GlobalSegurosColombia/posts/pfbid123", pagina) is None
    assert url_perfil_facebook("https://www.facebook.com/photo.php?fbid=1", pagina) is None
    assert url_perfil_facebook("/juan.gomez", pagina) == "https://www.facebook.com/juan.gomez"


def test_fusiona_like_y_comentario_de_la_misma_persona():
    pagina = "https://www.facebook.com/GlobalSeguros"
    personas = []
    fusionar(personas, {
        "href": "https://www.facebook.com/ana.perez",
        "nombre": "Ana Pérez",
        "tipo": "like",
        "publicacion": "Seguro de vida para tu familia",
        "pagina": pagina,
    })
    fusionar(personas, {
        "href": "https://www.facebook.com/ana.perez?comment_id=88",
        "nombre": "Ana Pérez",
        "tipo": "comentario",
        "texto": "Quiero saber de accidentes en moto",
        "publicacion": "Seguro de vida para tu familia",
        "pagina": pagina,
    })
    assert len(personas) == 1
    p = personas[0]
    assert p["likes"] == 1 and p["comentarios"] == 1
    assert p["perfil"] == "https://www.facebook.com/ana.perez"
    assert "accidentes" in p["textos"][0]
    texto = acercamiento(p, "Global Seguros")
    assert "Comentó" in texto
    assert "me gusta" in texto.lower()
    assert "accidentes" in texto.lower() or "Producto afín" in texto
    assert "facebook.com/ana.perez" in texto or "Messenger" in texto or "mensaje directo" in texto.lower()


def test_no_cuenta_a_la_pagina_como_interactuante():
    pagina = "https://www.facebook.com/GlobalSegurosColombia"
    personas = []
    fusionar(personas, {
        "href": pagina, "nombre": "Global Seguros", "tipo": "comentario",
        "texto": "Gracias", "pagina": pagina,
    })
    assert personas == []


def test_fusiona_share_con_like_y_comentario():
    pagina = "https://www.facebook.com/Mapfreco"
    personas = []
    fusionar(personas, {
        "href": "https://www.facebook.com/ana.perez", "nombre": "Ana Pérez",
        "tipo": "like", "pagina": pagina, "publicacion": "Viaja cubierto",
    })
    fusionar(personas, {
        "href": "https://www.facebook.com/ana.perez", "nombre": "Ana Pérez",
        "tipo": "compartido", "pagina": pagina, "publicacion": "Viaja cubierto",
    })
    p = personas[0]
    assert p["likes"] == 1 and p["compartidos"] == 1 and p["perfil"].endswith("/ana.perez")
    texto = acercamiento(p, "MAPFRE")
    assert "Compartió" in texto
    assert "me gusta" in texto.lower()


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
