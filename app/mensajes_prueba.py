"""Tres borradores de prueba por prospecto, después de analizar su perfil.

No se envían y no exigen correo ni celular: el asesor los revisa en la pestaña Mensajes.
Siempre hay tres, uno por cada eslogan de Global Seguros.
"""
import json

from psycopg2.extras import Json

from app import mensajes, validacion
from app.conocimiento import get_product_knowledge
from app.database import get_connection
from app.ollama_client import generate_json

DDL = """
CREATE TABLE IF NOT EXISTS public.mensajes_prueba (
    id_mensaje SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    fuente_url TEXT NOT NULL,
    red TEXT NOT NULL,
    producto TEXT NOT NULL,
    opcion SMALLINT NOT NULL,
    eslogan TEXT NOT NULL,
    cuerpo TEXT NOT NULL,
    estado TEXT NOT NULL,
    errores_validacion JSONB,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (nombre, opcion)
);
"""


def asegurar_tabla():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for sentencia in DDL.split(";"):
                if sentencia.strip():
                    cur.execute(sentencia)
        conn.commit()
    finally:
        conn.close()


def _cliente(nombre, producto, hechos):
    """Solo la condición general llega al modelo. No el detalle de familia, ciudad ni empresa."""
    textos = []
    for hecho in hechos or []:
        if hecho.get("categoria") in ("Trabajo", "Estudios", "Situacion actual"):
            textos.append(hecho.get("contenido") or "")
    condicion = mensajes.condicion_general({
        "nombre": nombre, "profesion": "", "hechos_perfil": "\n".join(textos),
    })
    return {"nombre": nombre, "producto_interes": producto, "profesion": condicion}


def respaldo(nombre, producto, eslogan):
    """Texto fijo que cumple las reglas si el modelo no responde."""
    corto = (nombre or "").split()[0] or "Hola"
    return (
        f"Hola {corto}. En Global Seguros podemos conversar sobre el {producto}: "
        f"te cuento para qué sirve y qué protege, solo con la información oficial del seguro. "
        f"¿Hablamos con un asesor cuando te quede bien?\n\n{eslogan}"
    )


def redactar_tres(nombre, producto, hechos, generar=None):
    """Tres opciones. Si el modelo falla, el respaldo completa hasta llegar a tres."""
    generar = generar or generate_json
    cliente = _cliente(nombre, producto, hechos)
    conocimiento = get_product_knowledge(producto)
    if conocimiento.startswith("No hay información"):
        conocimiento = f"Producto: {producto}. No agregues coberturas, precios ni cifras."
    opciones = []
    for i, eslogan in enumerate(mensajes.ESLOGANES, 1):
        errores, cuerpo = [], ""
        for _ in range(2):
            data = generar(mensajes._prompt(cliente, conocimiento, "whatsapp", errores, eslogan), temperature=0.4)
            if not isinstance(data, dict):
                errores = ["La respuesta no fue un JSON válido."]
                continue
            cuerpo = str(data.get("cuerpo") or "").strip().strip('"')
            errores = validacion.validar(cuerpo, "", "whatsapp", cliente, conocimiento)
            if not errores:
                break
        if not cuerpo or errores:
            cuerpo = respaldo(cliente["nombre"], producto, eslogan)
            errores = validacion.validar(cuerpo, "", "whatsapp", cliente, conocimiento)
        cuerpo_final = f"{cuerpo}\n\n{mensajes.PIE['whatsapp']}"
        opciones.append({
            "opcion": i,
            "eslogan": eslogan,
            "cuerpo": cuerpo_final,
            "estado": "borrador" if not errores else "requiere_revision",
            "errores": errores,
        })
    return opciones


def generar(nombre, url, red, producto, hechos, usuario=None):
    """Guarda las tres opciones de este prospecto y devuelve la lista."""
    if not (nombre and producto):
        return []
    print(f"Redactando 3 mensajes de prueba para {nombre} ({producto})…")
    opciones = redactar_tres(nombre, producto, hechos)
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.mensajes_prueba WHERE nombre = %s", (nombre,))
            for op in opciones:
                cur.execute("""INSERT INTO public.mensajes_prueba
                    (nombre, fuente_url, red, producto, opcion, eslogan, cuerpo, estado,
                     errores_validacion, creado_en)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, now())""",
                    (nombre, url, red, producto, op["opcion"], op["eslogan"], op["cuerpo"],
                     op["estado"], Json(op["errores"]) if op["errores"] else None))
        conn.commit()
    finally:
        conn.close()
    print(f"OK {nombre}: 3 mensajes de prueba listos.")
    return opciones


def _marca_tiempo(valor):
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return str(valor or "")


def agrupar(filas):
    """Un bloque por persona, el más reciente primero. No ordena por nombre."""
    grupos = {}
    for fila in filas:
        clave = fila.get("nombre") or ""
        marca = _marca_tiempo(fila.get("creado_en"))
        if clave not in grupos:
            grupos[clave] = {
                "nombre": fila.get("nombre") or "",
                "fuente_url": fila.get("fuente_url") or "",
                "red": fila.get("red") or "",
                "producto": fila.get("producto") or "",
                "creado_en": marca,
                "opciones": [],
            }
        elif marca > (grupos[clave]["creado_en"] or ""):
            grupos[clave]["creado_en"] = marca
            grupos[clave]["fuente_url"] = fila.get("fuente_url") or grupos[clave]["fuente_url"]
            grupos[clave]["red"] = fila.get("red") or grupos[clave]["red"]
            grupos[clave]["producto"] = fila.get("producto") or grupos[clave]["producto"]
        errores = fila.get("errores_validacion")
        if isinstance(errores, str):
            errores = json.loads(errores)
        grupos[clave]["opciones"].append({
            "opcion": fila.get("opcion"), "eslogan": fila.get("eslogan") or "",
            "cuerpo": fila.get("cuerpo") or "",
            "estado": fila.get("estado") or "", "errores": errores or [],
        })
    for g in grupos.values():
        g["opciones"].sort(key=lambda o: o["opcion"] or 0)
    return sorted(grupos.values(), key=lambda g: g["creado_en"] or "", reverse=True)


def listar():
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT nombre, fuente_url, red, producto, opcion, eslogan, cuerpo,
                                  estado, errores_validacion, creado_en, id_mensaje
                           FROM public.mensajes_prueba
                           ORDER BY creado_en DESC, id_mensaje DESC, opcion""")
            cols = [d[0] for d in cur.description]
            filas = [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()
    return agrupar(filas)
