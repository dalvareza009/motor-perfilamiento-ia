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


def hechos_desde_info(info):
    """Ficha del scraper -> mismos fragmentos que la ingesta de perfiles."""
    info = info or {}
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
    trabajo = _campo(info.get("experiencia"))
    if trabajo:
        perfil_redes._agregar(hechos, "Trabajo", trabajo)
    estudios = _campo(info.get("educacion"))
    if estudios:
        perfil_redes._agregar(hechos, "Estudios", estudios)
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
    edad = _campo(info.get("edad"))
    if edad:
        perfil_redes._agregar(hechos, "Edad", edad)
    logros = _campo(info.get("logros"))
    if logros:
        perfil_redes._agregar(hechos, "Logros", logros)
    interacciones = _campo(info.get("interacciones"))
    if interacciones:
        perfil_redes._agregar(hechos, "Interacciones", interacciones)
    cuenta, salida = {}, []
    for hecho in hechos:
        n = cuenta.get(hecho["categoria"], 0) + 1
        cuenta[hecho["categoria"]] = n
        titulo = hecho["categoria"] if n == 1 else f"{hecho['categoria']} ({n})"
        salida.append({**hecho, "titulo": titulo})
    salida.extend(redes_seguidas.hechos_de_red(info))
    return salida


def _persona(persona, info, url):
    if persona:
        return {
            "nombre": persona.get("nombre") or (info or {}).get("nombre") or url,
            "clave_cliente": persona.get("clave_cliente") or None,
        }
    return {"nombre": (info or {}).get("nombre") or url, "clave_cliente": None}


def persistir(persona, red, url, info, posts=None):
    """Escribe ficha, productos sugeridos y actividad en la base. Devuelve conteos."""
    asegurar_hechos()
    asegurar_actividad()
    quien = _persona(persona, info, url)
    hechos = hechos_desde_info(info)
    sugeridos = perfil_redes.sugerir_productos(hechos) if hechos else []
    fragmentos = hechos + sugeridos
    n = a = s = 0
    if fragmentos:
        n, a, s = _guardar(quien, red, url, fragmentos)

    nuevas = intereses = omitidas = 0
    for post in posts or []:
        texto = (post.get("texto") or "").strip()
        if not texto:
            continue
        evaluacion = linkedin_texto.evaluar_publicacion(texto)
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
