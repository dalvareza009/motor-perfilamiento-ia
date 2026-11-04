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
                    (nombre, fuente_url, red, producto, opcion, eslogan, cuerpo, estado, errores_validacion)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (nombre, url, red, producto, op["opcion"], op["eslogan"], op["cuerpo"],
                     op["estado"], Json(op["errores"]) if op["errores"] else None))
        conn.commit()
    finally:
        conn.close()
    print(f"OK {nombre}: 3 mensajes de prueba listos.")
    return opciones


def listar():
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT nombre, fuente_url, red, producto, opcion, eslogan, cuerpo,
                                  estado, errores_validacion, creado_en
                           FROM public.mensajes_prueba
                           ORDER BY creado_en DESC, nombre, opcion""")
            cols = [d[0] for d in cur.description]
            filas = [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()
    grupos, orden = {}, []
    for fila in filas:
        clave = fila["nombre"]
        if clave not in grupos:
            grupos[clave] = {
                "nombre": fila["nombre"], "fuente_url": fila["fuente_url"], "red": fila["red"],
                "producto": fila["producto"], "creado_en": fila["creado_en"].isoformat(),
                "opciones": [],
            }
            orden.append(clave)
        errores = fila["errores_validacion"]
        if isinstance(errores, str):
            errores = json.loads(errores)
        grupos[clave]["opciones"].append({
            "opcion": fila["opcion"], "eslogan": fila["eslogan"], "cuerpo": fila["cuerpo"],
            "estado": fila["estado"], "errores": errores or [],
        })
    return [grupos[c] for c in orden]
