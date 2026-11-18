"""Cada perfil se revisa entero para el dato de hijos. Certeza solo con declaración propia."""
from app.hijos import analizar, aplicar
from app.ingesta_actividad import hechos_desde_info
from app.perfil_redes import sugerir_productos


def _cats(hechos):
    return {h["categoria"]: h["contenido"] for h in hechos}


def test_bio_mama_de_es_certeza_alta():
    hallado = analizar({"bio": "Mamá de Valentina. Emprendedora."})
    assert hallado["certeza"] == "alta"
    assert "valentina" in hallado["resumen"].lower()
    hechos = hechos_desde_info({"bio": "Mamá de Valentina. Emprendedora."})
    por = _cats(hechos)
    assert "Hijos" in por
    assert "Indicio de hijos" not in por
    productos = {p["titulo"] for p in sugerir_productos(hechos)}
    assert "Seguro educativo" in productos
    assert "Seguro de vida" in productos


def test_caption_y_alt_de_foto_cuentan_como_hijos():
    posts = [{
        "tipo": "publicacion",
        "texto": "Graduación con mi hija en el colegio.",
        "tiene_imagenes": True,
        "alts": ["Foto con mi hija en el acto de grado"],
    }]
    hallado = analizar({}, posts)
    assert hallado["certeza"] == "alta"
    assert any(e["origen"] == "caption de foto" for e in hallado["evidencias"])
    por = _cats(hechos_desde_info({}, posts))
    assert "Hijos" in por
    solo_alt = analizar({}, [{
        "tipo": "publicacion", "texto": "",
        "alts": ["Con mi hija en el parque"], "tiene_imagenes": True,
    }])
    assert solo_alt["certeza"] == "alta"
    from app.perfil_redes import aplicar_lo_publicado
    ficha = aplicar_lo_publicado({}, [{
        "tipo": "publicacion", "texto": "",
        "alts": ["Con mi hija en el parque"],
    }])
    assert "hija" in (ficha.get("familia") or "").lower()


def test_hijo_etiquetado_en_facebook_es_certeza():
    info = {"familia": "Familia declarada en el perfil: Hijo: Pedro. Esposa: María Gómez"}
    hallado = analizar(info)
    assert hallado["certeza"] == "alta"
    assert "pedro" in hallado["resumen"].lower()


def test_compartir_maternidad_es_indicio_no_hecho():
    posts = [{
        "tipo": "compartida",
        "texto": "10 consejos de maternidad y crianza para el primer año.",
    }]
    hallado = analizar({}, posts)
    assert hallado["certeza"] == "indicio"
    por = _cats(hechos_desde_info({}, posts))
    assert "Indicio de hijos" in por
    assert "Hijos" not in por
    productos = {p["titulo"] for p in sugerir_productos(hechos_desde_info({}, posts))}
    assert "Seguro educativo" not in productos


def test_el_texto_original_de_un_repost_no_se_copia_como_hijos():
    posts = [{
        "tipo": "compartida",
        "texto": "Con mi hija celebramos su grado en la Universidad EAFIT.",
    }]
    hallado = analizar({}, posts)
    assert hallado["certeza"] == ""
    por = _cats(hechos_desde_info({}, posts))
    assert "Hijos" not in por
    assert "Indicio de hijos" not in por
    assert "Familia" not in por
    con_marca = analizar({}, [{
        "tipo": "compartida",
        "texto": "Reposteó. Con mi hija celebramos su grado en la Universidad EAFIT.",
    }])
    assert con_marca["certeza"] == ""


def test_si_escribe_mi_hija_al_compartir_queda_certeza_media():
    posts = [{
        "tipo": "compartida",
        "texto": "Feliz con mi hija en su primer día.\nReposteó una publicación de Crianza Feliz",
    }]
    hallado = analizar({}, posts)
    assert hallado["certeza"] == "media"
    por = _cats(hechos_desde_info({}, posts))
    assert "Hijos" in por


def test_no_inventa_por_familias_clientes_ni_por_su_hija():
    assert analizar({"experiencia": "Apoyo a las familias clientes desde 2020."})["certeza"] == ""
    assert analizar({}, [{"tipo": "publicacion", "texto": "Su hija se graduó hoy."}])["certeza"] == ""
    assert analizar({}, [{"tipo": "publicacion", "texto": "Feliz día de las madres a todas."}])["certeza"] == ""
    assert analizar({"bio": "Amante del ciclismo y el café"})["certeza"] == ""
    assert analizar({}, [{"tipo": "publicacion", "texto": "Soy padre en la parroquia."}])["certeza"] == ""
    assert analizar({}, [{"tipo": "publicacion", "texto": "Visité a mi padre de familia en Cali."}])["certeza"] == ""
    assert aplicar({}, [])["hijos_certeza"] == ""
    assert hechos_desde_info({}) == []
    assert hechos_desde_info(None) == []


def test_comentario_propio_mi_hijo_es_certeza():
    posts = [{"tipo": "publicacion", "texto": "Quiero un seguro para mi hijo."}]
    hallado = analizar({}, posts)
    assert hallado["certeza"] == "alta"
    por = _cats(hechos_desde_info({"titular": "Analista"}, posts))
    assert "Hijos" in por
    assert "Situacion actual" in por
    assert analizar({"bio": "Soy papá."})["certeza"] == "alta"


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
