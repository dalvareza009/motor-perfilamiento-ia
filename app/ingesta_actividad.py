"""Pasa la extracción con sesión (Facebook / Instagram / LinkedIn / X) a las tablas que ya usa el modelo.

La ficha y los productos sugeridos van a hechos_perfil (pendientes de revisión).
Las publicaciones con tema del catálogo van a publicaciones_linkedin + intereses_linkedin;
al aprobar un interés, se copia a hechos_perfil y el modelo lo lee.
No se escriben CSV: el asesor y los borradores leen PostgreSQL.
"""
import re

from app import linkedin_texto, perfil_redes, redes_seguidas
from app.ingesta_linkedin import (asegurar_tabla as asegurar_actividad, _guardar_interes,
                                  _guardar_publicacion)
from app.ingesta_perfiles import _guardar, asegurar_tabla as asegurar_hechos

_ETIQUETA = re.compile(
    r"^(trabajo|estudios|estado civil|edad|familia)\s+declarad[oa]s?\s+en el perfil:\s*", re.I)


def _deduplicar(texto):
    vistos, partes = set(), []
    for trozo in re.split(r"\s*[·.|]\s*", re.sub(r"\s+", " ", texto or "").strip(" .")):
        t = trozo.strip(" .")
        clave = perfil_redes._n(t)
        if t and clave not in vistos:
            vistos.add(clave)
            partes.append(t)
    return ". ".join(partes)


def _campo(texto):
    t = _ETIQUETA.sub("", (texto or "").strip())
    return _deduplicar(t)


def _hechos_de_campo(hechos, blob, default):
    """Parte un campo de ficha: cursos no van a estudios, empleos pasados no van a trabajo."""
    from app.tipo_dato import eje_ficha

    if not blob:
        return
    cubetas = {}
    for frase in perfil_redes._oraciones(blob):
        cat = eje_ficha(frase, seccion=default, default=default) or default
        cubetas.setdefault(cat, []).append(frase)
    for cat, partes in cubetas.items():
        perfil_redes._agregar(hechos, cat, ". ".join(partes))


def hechos_desde_info(info, posts=None, incluir_red=True):
    """Ficha de la persona (trabajo, estudios, familia…).

    Seguidores, seguidos, comentadores y páginas NO van en Revisión de hechos:
    quedan en «Seguidores e intereses» si incluir_red=True.
    """
    from app import hijos
    info = hijos.aplicar(info or {}, posts)
    hechos = []
    titular = _campo(info.get("titular"))
    if titular:
        perfil_redes._agregar(hechos, "Situacion actual", titular)
    bio = _campo(info.get("bio"))
    if bio and perfil_redes._n(bio) != perfil_redes._n(titular):
        perfil_redes._agregar(hechos, "Descripcion", bio)
    ubicacion = _campo(info.get("ubicacion"))
    if ubicacion:
        perfil_redes._agregar(hechos, "Ubicacion", ubicacion)
    _hechos_de_campo(hechos, _campo(info.get("experiencia")), "Trabajo")
    _hechos_de_campo(hechos, _campo(info.get("experiencia_pasada")), "Experiencia")
    _hechos_de_campo(hechos, _campo(info.get("educacion")), "Estudios")
    _hechos_de_campo(hechos, _campo(info.get("cursos")), "Cursos")
    extra = _campo(info.get("informacion"))
    if extra:
        perfil_redes._agregar(hechos, "Informacion", extra)
    civil = _campo(info.get("estado_civil"))
    if civil:
        perfil_redes._agregar(hechos, "Estado civil", civil)
    laboral = _campo(info.get("estado_laboral"))
    if laboral:
        perfil_redes._agregar(hechos, "Estado laboral", laboral)
    academico = _campo(info.get("estado_academico"))
    if academico:
        perfil_redes._agregar(hechos, "Estado academico", academico)
    familia = _campo(info.get("familia"))
    if familia:
        perfil_redes._agregar(hechos, "Familia", familia)
    for hecho in hijos.hechos_de(info):
        perfil_redes._agregar(hechos, hecho["categoria"], hecho["contenido"])
    edad = _campo(info.get("edad"))
    if edad:
        perfil_redes._agregar(hechos, "Edad", edad)
    ingresos = _campo(info.get("ingresos"))
    if ingresos:
        perfil_redes._agregar(hechos, "Ingresos", ingresos)
    logros = _campo(info.get("logros"))
    if logros:
        perfil_redes._agregar(hechos, "Logros", logros)
    cuenta, salida = {}, []
    for hecho in hechos:
        n = cuenta.get(hecho["categoria"], 0) + 1
        cuenta[hecho["categoria"]] = n
        titulo = hecho["categoria"] if n == 1 else f"{hecho['categoria']} ({n})"
        salida.append({**hecho, "titulo": titulo})
    if incluir_red:
        salida.extend(redes_seguidas.hechos_de_red(info, posts=posts))
    return salida


def _persona(persona, info, url):
    crudo = ""
    if persona:
        crudo = persona.get("nombre") or (info or {}).get("nombre") or ""
        clave = persona.get("clave_cliente") or None
    else:
        crudo = (info or {}).get("nombre") or ""
        clave = None
    return {"nombre": perfil_redes.nombre_de_perfil(crudo, url), "clave_cliente": clave}


def _guardar_perfiles_encontrados(info, dueno=""):
    """Otras redes ligadas van a URLs perfiles, no a Revisión de hechos."""
    from app import facebook_pagina
    origen = f"encontrado en {dueno}"[:80] if dueno else "otra red"
    for item in (info or {}).get("otras_redes") or []:
        url = (item or {}).get("url") or ""
        if url:
            try:
                facebook_pagina.agregar_recopilar(url, origen=origen)
            except Exception as e:
                print(f"No se guardó la URL {url}: {e}")


def persistir(persona, red, url, info, posts=None):
    """Escribe ficha, productos sugeridos y actividad en la base. Devuelve conteos.

    Guarda siempre, aunque la URL no esté en Personas autorizadas: hechos de
    ficha (incluido el dato de hijos), revisión de contenido y seguidores/intereses.
    """
    asegurar_hechos()
    asegurar_actividad()
    quien = _persona(persona, info, url)
    from app.contenido import describir_publicacion, resumir_actividad
    blobs = [
        (info or {}).get("bio"), (info or {}).get("titular"), (info or {}).get("acerca"),
        "\n".join(" ".join(p for p in (
            (post.get("texto") or ""), (post.get("enlaces") or ""),
            (post.get("texto_imagen") or ""), (post.get("descripcion_imagen") or ""),
        ) if p) for post in (posts or [])),
    ]
    from app.discernimiento import filtrar_posts
    posts = filtrar_posts(posts)
    info = perfil_redes.anexar_otras_redes(info or {}, "\n".join(p for p in blobs if p), red, url)
    _guardar_perfiles_encontrados(info, quien.get("nombre") or "")
    info = perfil_redes.aplicar_lo_publicado(info, posts)
    from app import hijos
    info = hijos.aplicar(info, posts)
    hechos = hechos_desde_info(info, posts)
    resumen_pub = resumir_actividad(posts)
    if resumen_pub:
        perfil_redes._agregar(hechos, "Resumen de contenido", resumen_pub)
    sugeridos = perfil_redes.sugerir_productos(hechos) if hechos else []
    fragmentos = hechos + sugeridos
    n = a = s = 0
    if fragmentos:
        n, a, s = _guardar(quien, red, url, fragmentos)

    nuevas = intereses = omitidas = 0
    from app.contenido import texto_mostrable
    for post in posts or []:
        texto = (post.get("texto") or "").strip()
        if not texto:
            texto = (post.get("descripcion_imagen") or post.get("texto_imagen") or "").strip()
        if not texto and post.get("tiene_imagenes"):
            texto = "Publicó una imagen."
        if not texto:
            continue
        limpio, estado = texto_mostrable(texto)
        if estado == "omitir":
            omitidas += 1
            continue
        desc = describir_publicacion({**post, "texto": limpio}) or {}
        post = {
            **post,
            "texto": desc.get("texto") or limpio,
            "resumen": desc.get("resumen") or "",
            "tiene_imagenes": bool(desc.get("tiene_imagenes") or post.get("tiene_imagenes")
                                   or post.get("imagenes")),
            "n_imagenes": int(desc.get("n_imagenes") or post.get("n_imagenes")
                              or len(post.get("imagenes") or []) or 0),
            "imagenes": post.get("imagenes") or [],
        }
        if estado != "ok":
            id_pub, es_nueva = _guardar_publicacion(quien, url, post, red=red)
            nuevas += int(es_nueva)
            omitidas += 1
            continue
        para_interes = " ".join(p for p in (
            limpio, post.get("texto_imagen"), post.get("descripcion_imagen")) if p)
        evaluacion = linkedin_texto.evaluar_publicacion(para_interes or limpio)
        if evaluacion["omitida"]:
            omitidas += 1
            continue
        id_pub, es_nueva = _guardar_publicacion(quien, url, post, red=red)
        nuevas += int(es_nueva)
        for interes in evaluacion["intereses"]:
            intereses += _guardar_interes(id_pub, quien, url, interes, red=red)

    print(f"OK {red} {url}: {n} hechos nuevos, {a} actualizados, {s} sin cambios; "
          f"{nuevas} publicaciones, {intereses} intereses pendientes, {omitidas} omitidas.")
    return {
        "hechos_nuevos": n,
        "hechos_actualizados": a,
        "hechos_iguales": s,
        "productos_sugeridos": [p["titulo"] for p in sugeridos],
        "publicaciones": nuevas,
        "intereses": intereses,
        "omitidas": omitidas,
    }
