"""Pruebas de perfiles públicos autorizados.  Ejecutar:  python -m tests.test_perfil_redes"""
from app.perfil_redes import (cargar_autorizados, categorias_oracion, ciudad_usable, clasificar_url,
                              quitar_fechas_iso,
                              contactos_de_ficha, contactos_de_texto, datos_para_cliente, es_muro_de_acceso,
                              es_perfil_privado, ficha_vacia, hechos_de_perfil, hechos_desde_ficha,
                              markdown_desde_ficha, sugerir_productos)

MD = """
# Daniela Álvarez

Analista de datos en Global Seguros

Medellín, Colombia

## Acerca de

Trabajo en el equipo de perfilamiento. Estudié ingeniería en la Universidad EAFIT. Madre de una hija.

## Experiencia

### Analista de datos

Global Seguros · 2022 - actualidad

Apoyo el perfilamiento de clientes.

## Educación

### Ingeniería de sistemas

Universidad EAFIT

## Aptitudes

Python, SQL

Sueldo confidencial: 8 millones
contacto@correo.com
"""


def test_solo_acepta_la_pagina_del_perfil():
    assert clasificar_url("https://www.linkedin.com/in/daniela-alvarez/")[0] == "linkedin"
    assert clasificar_url("https://www.instagram.com/dani/?hl=es")[1] == "https://www.instagram.com/dani/"
    assert clasificar_url("https://x.com/dani")[0] == "x"
    assert clasificar_url("https://www.tiktok.com/@dani")[0] == "tiktok"
    assert clasificar_url("https://www.linkedin.com/search/results/all/?keywords=dani") is None
    assert clasificar_url("https://www.instagram.com/p/ABC123/") is None
    assert clasificar_url("https://www.facebook.com/messages/t/1") is None
    assert clasificar_url("https://www.facebook.com/ana")[1] == "https://www.facebook.com/ana"
    assert (clasificar_url("https://www.facebook.com/profile.php?id=61596287095349")[1]
            == "https://www.facebook.com/profile.php?id=61596287095349")
    assert clasificar_url("https://www.globalseguroscolombia.com/productos/") is None
    assert clasificar_url("https://www.linkedin.com/in/REEMPLAZAR") is None


def test_exige_autorizacion_explicita():
    personas, avisos = cargar_autorizados([
        {"nombre": "Ana", "autorizado": False, "autorizacion": "Autorización directa suficiente.",
         "urls": ["https://www.linkedin.com/in/ana"]},
        {"nombre": "Luis", "autorizado": True, "autorizacion": "corta",
         "urls": ["https://www.linkedin.com/in/luis"]},
        {"nombre": "Marta Gómez", "autorizado": True, "clave_cliente": "C1",
         "autorizacion": "Autorización directa para leer el perfil público.",
         "urls": ["https://www.instagram.com/marta/", "https://www.instagram.com/p/XYZ/"]},
    ])
    assert personas == [{
        "nombre": "Marta Gómez",
        "clave_cliente": "C1",
        "autorizacion": "Autorización directa para leer el perfil público.",
        "urls": [{"red": "instagram", "url": "https://www.instagram.com/marta/"}],
    }]
    assert len(avisos) == 3


def test_extrae_trabajo_estudios_familia_y_ciudad():
    hechos = hechos_de_perfil(MD)
    texto = " ".join(f"{h['categoria']}|{h['contenido']}" for h in hechos)
    assert "Trabajo|" in texto and "Global Seguros" in texto
    assert "Estudios|" in texto and "EAFIT" in texto
    assert "Familia|" in texto and "hija" in texto
    assert "Ubicacion|" in texto and "Medellín" in texto
    assert "Sueldo" not in texto and "correo.com" not in texto and "Python" not in texto


def test_no_inventa_familia_por_una_frase_de_trabajo():
    md = "## Experiencia\n\nAnalista de servicio. Apoyo a las familias clientes desde 2020 en Medellín."
    cats = {h["categoria"] for h in hechos_de_perfil(md)}
    assert "Familia" not in cats
    assert "Trabajo" in cats


def test_lo_publicado_completa_edad_estado_civil_lugar_y_situacion():
    from datetime import date
    from app.perfil_redes import aplicar_lo_publicado
    info = aplicar_lo_publicado({}, [
        {"tipo": "publicacion", "texto": (
            "Vivo en Medellín. Estoy casada. Tengo 34 años. "
            "Soy estudiante de maestría. Estoy desempleada."
        )},
        {"tipo": "publicacion", "texto": "Nací en 1990 y sigo por aquí."},
        {"tipo": "compartida", "texto": "Estoy soltero y vivo en Bogotá. Tengo 22 años."},
        {"tipo": "publicacion", "texto": "De vacaciones en Cartagena con mi hija de 8 años."},
    ], hoy=date(2026, 11, 3))
    assert "Medellín" in info["ubicacion"]
    assert "Bogotá" not in info.get("ubicacion", "")
    assert "Cartagena" not in info.get("ubicacion", "")
    assert "casada" in info["estado_civil"].lower()
    assert "soltero" not in info["estado_civil"].lower()
    assert "34 años" in info["edad"] or "Tengo 34 años" in info["edad"]
    assert "36 años" in info["edad"]
    assert "8 años" not in info["edad"]
    assert "estudiante" in (info.get("estado_academico") or info.get("educacion") or "").lower()
    assert "desempleada" in (info.get("estado_laboral") or "").lower()
    assert "hija" in (info.get("familia") or "").lower()


def test_del_caption_sale_graduacion_y_trabajo_propios():
    from app.perfil_redes import aplicar_lo_publicado, detectar_otras_redes
    info = aplicar_lo_publicado(
        {"educacion": "Universidad de Pamplona", "experiencia": "Autónomo"},
        [{"tipo": "publicacion", "texto": "Me gradué de la maestría. Trabajo como analista en Global."}],
    )
    assert "maestr" in (info.get("educacion") or info.get("estado_academico") or "").lower()
    assert "analista" in (info.get("experiencia") or "").lower()
    suelta = aplicar_lo_publicado(
        {"educacion": "Universidad de Pamplona", "experiencia": "Autónomo"},
        [{"tipo": "publicacion", "texto": "Pasé la tarde en la universidad con amigos del colegio."}],
    )
    assert suelta["educacion"] == "Universidad de Pamplona"
    assert "colegio" not in suelta["educacion"]
    assert suelta["experiencia"] == "Autónomo"
    otras = detectar_otras_redes(
        "Mi Instagram: https://www.instagram.com/ana.g/ y también https://x.com/ana",
        "facebook", "https://www.facebook.com/ana")
    redes = {o["red"] for o in otras}
    assert "instagram" in redes and "x" in redes


def test_la_ficha_si_llena_estudios_y_cargo():
    from app.perfil_redes import aplicar_lo_publicado
    info = aplicar_lo_publicado({}, [
        {"tipo": "publicacion", "texto": "Analista en Global. Estudié en la Universidad EAFIT."},
    ], origen="ficha")
    assert "Analista" in info["experiencia"]
    assert "EAFIT" in info["educacion"]


def test_estudiar_no_cuenta_como_trabajo_actual():
    cats = categorias_oracion("Estudié ingeniería en la Universidad EAFIT.", "Situacion actual")
    assert cats == ["Estudios"]


def test_muro_de_acceso_no_produce_hechos():
    muro = "Sign in to view this profile. Join to view the full experience of this member."
    assert es_muro_de_acceso(muro)
    assert hechos_de_perfil(muro) == []


def test_decodifica_el_slug_de_linkedin():
    red, url = clasificar_url("https://www.linkedin.com/in/daniela-%C3%A1lvarez-acevedo-091984380/")
    assert red == "linkedin"
    assert url == "https://www.linkedin.com/in/daniela-álvarez-acevedo-091984380"


def test_la_ficha_trae_trabajo_estudios_y_bio_sin_contacto():
    ficha = {"people": [{
        "full_name": "Daniela Alvarez",
        "headline": "Analista de datos en Global Seguros",
        "description": "Madre de una hija. Estudié en la Universidad EAFIT.",
        "location": {"city": "Medellín", "country": "Colombia"},
        "employment": {"current": {"title": "Analista de datos", "company_name": "Global Seguros"}},
        "educations": [{"school_name": "Universidad EAFIT", "degree": "Ingeniería de sistemas"}],
        "email": "secreto@correo.com",
        "skills": ["Python"],
    }]}
    hechos = hechos_de_perfil(markdown_desde_ficha(ficha))
    texto = " ".join(f"{h['categoria']}|{h['contenido']}" for h in hechos)
    assert "Trabajo|" in texto and "Global Seguros" in texto
    assert "Estudios|" in texto and "EAFIT" in texto
    assert "Familia|" in texto and "hija" in texto
    assert "Ubicacion|" in texto and "Medellín" in texto
    assert "correo.com" not in texto and "Python" not in texto


def test_enriquecimiento_masivo_trae_cargo_y_empresa_sin_correo():
    ficha = {"matches": [{
        "name": "Ana Gómez",
        "title": "Analista de datos",
        "email": "ana@correo.com",
        "email_status": "verified",
        "organization": {"name": "Global Seguros", "phone": "+57 300 123 4567"},
        "employment_history": [
            {"title": "Analista de datos", "organization_name": "Global Seguros"},
        ],
    }, None]}
    hechos = hechos_de_perfil(markdown_desde_ficha(ficha))
    texto = " ".join(f"{h['categoria']}|{h['contenido']}" for h in hechos)
    assert "Trabajo|" in texto and "Global Seguros" in texto and "Analista de datos" in texto
    assert "correo.com" not in texto and "300" not in texto
    assert ficha_vacia({"matches": [None]})


def test_ficha_vacia_cuando_el_indice_no_tiene_a_la_persona():
    assert ficha_vacia({"people": [], "metadata": {}})
    assert ficha_vacia({"data": []})
    assert not ficha_vacia({"people": [{"full_name": "Ana", "headline": "Analista"}]})


def test_instagram_privado_no_se_lee():
    ficha = {"data": [{"handle": "daa0926", "bio": "Madre de una hija", "isPrivate": True}]}
    assert es_perfil_privado(ficha)
    assert markdown_desde_ficha(ficha) == ""


def test_el_contacto_es_de_la_persona_y_no_de_la_empresa():
    ficha = {"people": [{
        "full_name": "Ana Gómez",
        "email": "ana@correo.com",
        "phone": "+57 300 123 4567",
        "organization": {"name": "Global Seguros", "phone": "+57 601 744 0084"},
    }]}
    contactos = {(c["titulo"], c["contenido"]) for c in contactos_de_ficha(ficha)}
    assert ("Correo", "ana@correo.com") in contactos
    assert ("Celular", "3001234567") in contactos
    assert all("7440084" not in valor for _, valor in contactos)
    assert "correo.com" not in markdown_desde_ficha(ficha)
    assert "3001234567" not in markdown_desde_ficha(ficha)
    texto = contactos_de_texto("Bio\nCelular +57 310 555 0199 y ana@correo.com")
    assert {c["contenido"] for c in texto} >= {"3105550199", "ana@correo.com"}


def test_la_ficha_guarda_todos_los_datos_personales_que_vienen_llenos():
    ficha = {"matches": [{
        "name": "Ana Gómez",
        "headline": "Madre de una hija. Tengo 34 años.",
        "title": "Analista de datos",
        "city": "Medellín",
        "state": "Antioquia",
        "country": "Colombia",
        "organization_id": "54a121c769702d8ccca1e802",
        "email": "ana@correo.com",
        "employment_history": [{
            "title": "Analista de datos",
            "organization_name": "Global Seguros",
            "organization_id": "54a121c769702d8ccca1e802",
            "start_date": "2022",
            "degree": None,
            "description": "Casada y con una hija.",
        }],
        "educations": [{"degree": "Ingeniería", "school_name": "Universidad EAFIT"}],
        "age": 34,
        "marital_status": "Casada",
    }]}
    hechos = hechos_desde_ficha(ficha)
    texto = " ".join(f"{h['categoria']}|{h['contenido']}" for h in hechos)
    assert "Ubicacion|Medellín, Antioquia, Colombia" in texto
    assert "Trabajo|" in texto and "Analista de datos en Global Seguros" in texto
    assert "Estudios|" in texto and "EAFIT" in texto
    assert "Familia|" in texto and "hija" in texto and "Casada" in texto
    assert "Edad|34 años" in texto
    assert "54a121c769702d8ccca1e802" not in texto
    assert ("Correo", "ana@correo.com") in {(c["titulo"], c["contenido"]) for c in contactos_de_ficha(ficha)}


def test_el_rango_iso_de_empleo_no_se_guarda():
    ficha = {"people": [{
        "full_name": "Ana Gómez",
        "employment_history": [{
            "title": "Analista de datos",
            "organization_name": "Global Seguros",
            "start_date": "2022-08-01T00:00:00Z",
            "end_date": "2023-02-01T00:00:00Z",
            "description": "Lideré el equipo (2022-08-01T00:00:00Z - 2023-02-01T00:00:00Z) de datos.",
        }],
    }]}
    hechos = hechos_desde_ficha(ficha)
    texto = " ".join(h["contenido"] for h in hechos)
    assert "Analista de datos en Global Seguros" in texto
    assert "T00:00:00Z" not in texto
    assert "2022-08-01" not in texto
    assert quitar_fechas_iso(
        "Lideré el equipo (2022-08-01T00:00:00Z - 2023-02-01T00:00:00Z) de datos."
    ) == "Lideré el equipo de datos."
    assert quitar_fechas_iso("(2022-08-01T00:00:00Z - 2023-02-01T00:00:00Z") == ""
    assert quitar_fechas_iso("Analista (2026-09-01 - None) en Global") == "Analista en Global"
    assert quitar_fechas_iso("Senior Power Systems Engineer - None)") == "Senior Power Systems Engineer"
    assert quitar_fechas_iso("(2026-09-01 - null)") == ""
    assert quitar_fechas_iso("Cargo (None - 2024-01-15)") == "Cargo"
    assert quitar_fechas_iso("Global Seguros · 2022 - actualidad") == "Global Seguros · 2022 - actualidad"


def test_fecha_de_sistema_con_none_no_se_guarda():
    ficha = {"people": [{
        "full_name": "Ana Gómez",
        "employment_history": [
            {
                "title": "Analista de datos",
                "organization_name": "Global Seguros",
                "start_date": "2026-09-01",
                "end_date": "None",
            },
            {
                "title": "Practicante",
                "organization_name": "Global Seguros",
                "start_date": "2022",
                "end_date": None,
            },
        ],
    }]}
    hechos = hechos_desde_ficha(ficha)
    texto = " ".join(h["contenido"] for h in hechos)
    assert "Analista de datos en Global Seguros" in texto
    assert "2026-09-01" not in texto
    assert "None" not in texto
    assert "Practicante en Global Seguros (2022 - actualidad)" in texto


def test_datos_de_cliente_salen_de_hechos_aprobados():
    hechos = [
        {"categoria": "Situacion actual", "titulo": "Situacion actual",
         "contenido": "Systems Engineering student at EAFIT University"},
        {"categoria": "Ubicacion", "titulo": "Ubicacion", "contenido": "Colombia, CO, Medellín, Antioquia"},
        {"categoria": "Estudios", "titulo": "Estudios", "contenido": "Universidad EAFIT"},
        {"categoria": "Producto sugerido", "titulo": "Seguro educativo", "contenido": "Estudios: Universidad EAFIT"},
    ]
    datos = datos_para_cliente(hechos)
    assert datos["profesion"] == "Estudiante"
    assert datos["ciudad"] == "Medellín"
    assert datos["universidad"] == "Universidad EAFIT"
    assert datos["producto_interes"] == "Seguro educativo"
    assert ciudad_usable("Medellín") == "Medellín"


def test_sugerencias_salen_del_hecho_explicito():
    hechos = hechos_de_perfil(MD)
    productos = {s["titulo"]: s["contenido"] for s in sugerir_productos(hechos)}
    assert "Seguro educativo" in productos and "EAFIT" in productos["Seguro educativo"]
    assert "hija" in productos["Seguro educativo"]
    assert "Seguro de vida" in productos and "Seguro de accidentes personales" in productos
    assert "Seguro de pensión" not in productos


def test_lote_acepta_urls_sin_estar_en_el_archivo():
    from app.ingesta_perfiles import objetivos_desde_urls
    objetivos, avisos = objetivos_desde_urls([
        "https://www.instagram.com/ana/",
        "https://x.com/ana",
        "no-es-url",
        "https://www.instagram.com/ana/",
    ], data=[])
    assert [p[1]["red"] for p in objetivos] == ["instagram", "x"]
    assert objetivos[0][0]["nombre"] == ""
    assert any("no reconocida" in a for a in avisos)


def test_lote_solo_usa_las_urls_pegadas():
    from app.ingesta_perfiles import objetivos_de_pedido
    vieja = {
        "nombre": "Persona vieja",
        "autorizado": True,
        "autorizacion": "Autorización directa para leer el perfil público.",
        "urls": ["https://www.instagram.com/vieja/"],
    }
    objetivos, _ = objetivos_de_pedido(
        urls=["https://x.com/nueva"], data=[vieja])
    assert [p[1]["url"] for p in objetivos] == ["https://x.com/nueva"]
    vacio, avisos = objetivos_de_pedido(urls=[], nombres=[], todos=False, data=[vieja])
    assert vacio == []
    assert avisos
    todas, _ = objetivos_de_pedido(todos=True, data=[vieja])
    assert [p[1]["url"] for p in todas] == ["https://www.instagram.com/vieja/"]


def test_registrar_une_por_nombre_y_completa_urls():
    import json
    import tempfile
    from pathlib import Path
    from app import ingesta_perfiles
    original = ingesta_perfiles.ARCHIVO
    with tempfile.TemporaryDirectory() as tmp:
        ingesta_perfiles.ARCHIVO = Path(tmp) / "perfiles_autorizados.json"
        try:
            ingesta_perfiles.registrar_perfil_leido(
                "Ana Gómez", "instagram", "https://www.instagram.com/ana/")
            ingesta_perfiles.registrar_perfil_leido(
                "Ana Gómez", "x", "https://x.com/ana")
            data = json.loads(ingesta_perfiles.ARCHIVO.read_text(encoding="utf-8"))
            assert len(data) == 1
            assert data[0]["nombre"] == "Ana Gómez"
            assert data[0]["autorizado"] is True
            assert len(data[0]["urls"]) == 2
        finally:
            ingesta_perfiles.ARCHIVO = original


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
