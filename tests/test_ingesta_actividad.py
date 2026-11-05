"""La extracción con sesión se convierte en hechos de perfil, no en CSV."""
from app.ingesta_actividad import hechos_desde_info
from app.perfil_redes import sugerir_productos


def test_ficha_facebook_sale_como_hechos_del_modelo():
    info = {
        "nombre": "Yimy Osvaldo Alvarez Gomez",
        "titular": "Autónomo",
        "ubicacion": "Vive en Segovia (Antioquia). De Remedios",
        "experiencia": "Trabajo declarado en el perfil: Autónomo. Autónomo. Autónomo",
        "educacion": ("Estudios declarados en el perfil: liceo ignacio yepes yepes. "
                      "Universidad de Pamplona. liceo ignacio yepes yepes. "
                      "Universidad de Pamplona. Universidad Distrital Francisco José de Caldas"),
        "estado_civil": "Estado civil declarado en el perfil: Casado. Casado desde 28 de febrero de 2010",
        "familia": "Familia declarada en el perfil: Hermana María Gómez",
        "edad": "Edad declarada en el perfil: 36 años",
    }
    hechos = hechos_desde_info(info)
    por = {h["titulo"]: h["contenido"] for h in hechos}
    assert por["Situacion actual"] == "Autónomo"
    assert "Segovia" in por["Ubicacion"] and "Remedios" in por["Ubicacion"]
    assert por["Trabajo"] == "Autónomo"
    assert "Universidad de Pamplona" in por["Estudios"]
    assert por["Estudios"].count("Universidad de Pamplona") == 1
    assert "Casado" in por["Estado civil"]
    assert "María Gómez" in por["Familia"]
    assert por["Edad"] == "36 años"
    productos = {s["titulo"]: s["contenido"] for s in sugerir_productos(hechos)}
    assert "Seguro de vida" in productos and "Casado" in productos["Seguro de vida"]
    assert "Seguro educativo" in productos


def test_la_bio_queda_como_descripcion():
    hechos = hechos_desde_info({
        "titular": "Analista",
        "bio": "Amante del ciclismo y el café en Medellín",
    })
    por = {h["categoria"]: h["contenido"] for h in hechos}
    assert por["Situacion actual"] == "Analista"
    assert "ciclismo" in por["Descripcion"]


def test_ficha_vacia_no_inventa_hechos():
    assert hechos_desde_info({}) == []
    assert hechos_desde_info(None) == []


def test_el_volcado_tecnico_y_el_aviso_no_se_muestran():
    from app.contenido import NOTA_NO_DISPONIBLE, NOTA_NO_ELEGIBLE, texto_mostrable
    json_ig = (
        '{"require":[["qplTimingsServerJS",null,null,["7704519671677679056","splash_screen_show"]]],'
        '"HasteSupportData":{"handle":null},"clpData":{"3729":{"r":1,"s":1}}}'
    )
    texto, estado = texto_mostrable(json_ig)
    assert estado == "no_elegible"
    assert texto == NOTA_NO_ELEGIBLE
    assert "qplTimings" not in texto
    aviso = (
        "a\n6\nEste contenido no está disponible en este momento\n"
        "Por lo general, esto sucede porque el propietario ha compartido "
        "el contenido solo con un grupo reducido de personas.\n6\nEscribe algo...\n"
        "Perfil  4/11/2026, 10:12 p. m."
    )
    texto, estado = texto_mostrable(aviso)
    assert estado == "no_disponible"
    assert texto == NOTA_NO_DISPONIBLE
    assert "Escribe algo" not in texto
    limpio, estado = texto_mostrable("Con mi hija celebramos su grado en Medellín.")
    assert estado == "ok"
    assert "hija" in limpio
    pie = (
        "Empleo\nAyuda\nAPI\nPrivacidad\nCondiciones\nUbicaciones\nPopular\n"
        "Instagram Lite\nMeta AI\nMuse\nSubir contactos y personas no usuarias\n"
        "Español (España)\nAfrikaans\nEnglish\nEnglish (UK)\nDeutsch"
    )
    texto, estado = texto_mostrable(pie)
    assert estado == "omitir"
    assert "Privacidad" not in texto
    assert "Meta AI" not in texto
    mixto, estado = texto_mostrable("Feliz de celebrar con mi hija.\nPrivacidad\nCondiciones\nEnglish")
    assert estado == "ok"
    assert "hija" in mixto
    assert "Privacidad" not in mixto


def test_describe_caption_acotado_e_imagen():
    from app.contenido import acotar, describir_publicacion, resumir_actividad
    largo = "Feliz de celebrar con mi hija en el parque " * 20
    assert acotar(largo, 40).endswith("…")
    d = describir_publicacion({
        "texto": "Salí en bici con el grupo de ciclismo del trabajo.",
        "tiene_imagenes": True,
        "n_imagenes": 2,
    })
    assert d["tiene_imagenes"] is True
    assert "imágenes" in d["resumen"].lower() or "imagen" in d["resumen"].lower()
    assert "deporte" in d["resumen"].lower()
    resumen = resumir_actividad([
        {"texto": "Con mi hija en casa.", "tiene_imagenes": True, "n_imagenes": 1},
        {"texto": "En el gimnasio hoy.", "tiene_imagenes": False},
    ])
    assert "2 pieza" in resumen
    assert "imagen" in resumen.lower()


def test_una_mencion_suelta_no_se_guarda_como_estudios():
    from app.contenido import CATEGORIAS_CONTENIDO, excluidas_de_ficha, quitar_ver_mas
    from app.perfil_redes import aplicar_lo_publicado
    info = aplicar_lo_publicado(
        {"educacion": "Universidad de Pamplona", "experiencia": "Autónomo"},
        [{"tipo": "publicacion", "texto": "Pasé la tarde en la universidad. Ver más"}],
    )
    assert info["educacion"] == "Universidad de Pamplona"
    assert "gerente" not in (info.get("experiencia") or "")
    hechos = hechos_desde_info(info)
    por = {h["categoria"]: h["contenido"] for h in hechos}
    assert "Pamplona" in por["Estudios"]
    assert "Publicacion" in CATEGORIAS_CONTENIDO
    assert "Estudios" not in excluidas_de_ficha()
    assert "Comentario" in excluidas_de_ficha()
    assert "Ver más" not in quitar_ver_mas("Feliz de graduarme de la maestría. Ver más")
    otras = hechos_desde_info({
        "otras_redes": [{"red": "instagram", "url": "https://www.instagram.com/ana/"}],
    })
    assert any("Instagram" in h["contenido"] and "scrapear" in h["contenido"] for h in otras)


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
