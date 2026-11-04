"""Generación y ciclo de vida de borradores de mensajes (el asesor revisa; nada se envía desde aquí)."""
import json
import random

from psycopg2 import sql
from psycopg2.extras import Json

from app import validacion
from app.conocimiento import get_product_knowledge
from app.database import get_connection
from app.ollama_client import MODEL, generate_json
from app.perfil_redes import normalizar_celular
from app.segmentos import CONSENT_COLUMN

VERSION_PROMPT = "v4"
MARCA = "Global Seguros"
# Los tres eslóganes oficiales (principal + campaña) viven en validacion.py;
# por cada mensaje se elige UNO al azar y ese mismo se exige al validar.
ESLOGANES = validacion.ESLOGANES
MAX_INTENTOS = 3
ACTIVOS = ("borrador", "requiere_revision", "aprobado")
TRANSICIONES = {
    "borrador": {"aprobado", "descartado"},
    "requiere_revision": {"descartado"},
    "aprobado": {"enviado", "descartado"},
}
# PENDIENTE: texto definido por el área legal / el encargado. Esto es solo un marcador.
PIE = {
    "correo": "Si prefieres no recibir más mensajes, respóndenos a este correo y lo tendremos en cuenta.",
    "whatsapp": "Si prefieres no recibir más mensajes, respóndenos y lo tendremos en cuenta.",
}
COLS_CLIENTE = ["clave_cliente", "nombre", "genero", "edad", "ciudad", "profesion", "universidad",
                "producto_interes", "tiene_correo", "tiene_celular", "correo", "celular"]


# ------------------------------------------------------------------ consultas
def buscar_cliente(texto):
    """Por clave (CL000123), nombre, correo o celular."""
    t = texto.strip()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT clave_cliente, nombre, ciudad FROM public.clientes_segmentados
                           WHERE clave_cliente = %s OR nombre ILIKE %s OR correo = LOWER(%s) OR celular = %s
                           ORDER BY nombre LIMIT 6""",
                        (t, f"%{t}%", t, normalizar_celular(t)))
            return cur.fetchall()
    finally:
        conn.close()


def obtener_cliente(clave):
    cols = COLS_CLIENTE + ([CONSENT_COLUMN] if CONSENT_COLUMN else [])
    q = sql.SQL("SELECT {c} FROM public.clientes_segmentados WHERE clave_cliente = %s").format(
        c=sql.SQL(", ").join(map(sql.Identifier, cols)))
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(q, (clave,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    d = dict(zip(cols, row))
    d["consentimiento"] = bool(d.pop(CONSENT_COLUMN)) if CONSENT_COLUMN else True
    return d


def _activo(clave, producto, canal):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id_mensaje, estado FROM public.mensajes
                           WHERE clave_cliente = %s AND LOWER(producto) = LOWER(%s) AND canal = %s
                             AND estado IN %s""", (clave, producto, canal, ACTIVOS))
            return cur.fetchone()
    finally:
        conn.close()


# ------------------------------------------------------------------ generación
def _sin_tildes(texto):
    import unicodedata
    t = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def condicion_general(cliente):
    """Condición amplia y no invasiva: 'estudiante', 'persona que trabaja', etc.

    Nunca devuelve universidad, empresa, institución, cargo detallado ni ciudad:
    esos datos existen en el perfil, pero nombrarlos en un mensaje suena a
    vigilancia. Saber que alguien es estudiante o trabajador es suficiente.
    """
    texto = _sin_tildes(" ".join(str(cliente.get(k) or "") for k in
                                 ("profesion", "hechos_perfil", "ocupacion")))
    if not texto.strip():
        return ""
    if any(p in texto for p in ("estudiant", "student", "estudia", "alumno", "escolar")):
        return "estudiante"
    if any(p in texto for p in ("pension", "jubil", "retirad")):
        return "persona pensionada"
    if any(p in texto for p in ("independiente", "autonom", "emprendedor", "freelance", "propio negocio")):
        return "persona independiente"
    if any(p in texto for p in ("docente", "profesor", "maestro", "ensen")):
        return "docente"
    if any(p in texto for p in ("trabaj", "emplead", "labor", "works", "working", "profesion",
                                 "ingenier", "medic", "abogad", "contador", "administrador",
                                 "analista", "desarrollador", "arquitect", "disenador")):
        return "persona que trabaja"
    return "profesional" if str(cliente.get("profesion") or "").strip() else ""


def _prompt(cliente, conocimiento, canal, errores_previos, eslogan=None):
    nombre = cliente["nombre"].split()[0]
    eslogan = eslogan or random.choice(ESLOGANES)
    condicion = condicion_general(cliente)
    if condicion:
        bloque_condicion = (
            f"CONDICIÓN GENERAL DEL CLIENTE (única personalización permitida): {condicion}. "
            "Puedes aludir a ella con naturalidad (p. ej. «como estudiante…» o «en tu etapa laboral…»), "
            "sin dar ningún detalle más concreto.\n"
        )
        regla_personal = ("No supongas situaciones personales que no se sigan de esa condición "
                          "general (hijos, familia, estado civil, necesidades).")
    else:
        bloque_condicion = ""
        regla_personal = "No supongas situaciones personales (hijos, familia, estado civil, necesidades)."
    if canal == "whatsapp":
        formato = ("Canal: WhatsApp. Entre 50 y 70 palabras EN TOTAL (incluido el eslogan), tono "
                   "cercano y natural, en 3 o 4 frases cortas y sin saludo formal. Estructura: saludo "
                   "con el nombre; una explicación MUY resumida del seguro (qué protege o paga y para "
                   "qué sirve, solo con la información del producto); una pregunta breve que invite a "
                   "conversar con un asesor de Global Seguros; y cierra con este eslogan EXACTO: "
                   f'"{eslogan}". Deja "asunto" vacío.')
    else:
        formato = ("Canal: correo. Asunto de máximo 10 palabras. Cuerpo entre 90 y 130 palabras: saludo "
                   "con el nombre; una explicación breve y clara del seguro (qué protege o paga, para "
                   "qué sirve y, si el producto lo dice, por cuánto tiempo); una invitación explícita a "
                   "conversar con un asesor de Global Seguros; y en una línea final aparte este eslogan "
                   f'EXACTO: "{eslogan}". Sin firma personal.')
    correccion = ""
    if errores_previos:
        correccion = ("\nTu intento anterior fue rechazado por estos motivos; corrígelos:\n- "
                      + "\n- ".join(errores_previos))
    return f"""Eres un asistente que redacta BORRADORES de mensajes para que un asesor de Global Seguros
contacte a un cliente. El asesor los revisará antes de usarlos.

CLIENTE: se llama {nombre}.
{bloque_condicion}
PRODUCTO: {cliente['producto_interes']}
INFORMACIÓN DEL PRODUCTO (única fuente permitida):
{conocimiento}

{formato}

REGLAS:
- Usa el nombre {nombre}.
- Preséntate siempre como {MARCA}: el mensaje debe nombrar a {MARCA} y llevar su huella.
- Cierra SIEMPRE invitando a conversar con un asesor (pregunta breve y sin presión).
- Explica el seguro de forma muy resumida: qué protege o paga y para qué sirve. Sin
  listas largas de coberturas, sin precios y sin cifras que no estén en el producto.
- Usa solo la información del producto; no inventes coberturas, beneficios, precios ni cifras.
- {regla_personal}
- PRIVACIDAD: aunque conozcas datos concretos del cliente, NUNCA menciones nombres de
  universidades, colegios, empresas, empleadores, instituciones o lugares donde estudia o
  trabaja, ni su cargo detallado, ni su ciudad. Mencionarlos suena invasivo. Solo vale la
  condición general indicada arriba (estudiante, persona que trabaja, etc.).
- No menciones salario, cómo se obtuvo el contacto, perfiles, segmentos ni datos internos.
- No uses marcadores como [nombre] ni {{nombre}}.
{correccion}
Responde SOLO con JSON: {{"asunto": "...", "cuerpo": "..."}}"""


def generar_para_cliente(cliente, canal, usuario):
    """Devuelve un dict con 'estado_proceso': generado | existente | omitido."""
    clave, producto = cliente["clave_cliente"], cliente["producto_interes"]

    if not cliente["consentimiento"]:
        return {"estado_proceso": "omitido", "motivo": "sin consentimiento registrado"}
    if canal == "correo" and not cliente["tiene_correo"]:
        return {"estado_proceso": "omitido", "motivo": "sin correo válido"}
    if canal == "whatsapp" and not cliente["tiene_celular"]:
        return {"estado_proceso": "omitido", "motivo": "sin celular válido"}
    if not producto:
        return {"estado_proceso": "omitido", "motivo": "sin producto de interés"}

    previo = _activo(clave, producto, canal)
    if previo:
        return {"estado_proceso": "existente", "id": previo[0], "estado": previo[1]}

    conocimiento = get_product_knowledge(producto)
    if conocimiento.startswith("No hay información"):
        return {"estado_proceso": "omitido", "motivo": f"sin base de conocimiento para '{producto}'"}

    from app.ingesta_perfiles import hechos_explicitos
    hechos = hechos_explicitos(clave, cliente.get("nombre"))
    if hechos:
        cliente = dict(cliente)
        cliente["hechos_perfil"] = "\n".join(f"- {h['categoria']}: {h['contenido']}" for h in hechos)

    eslogan = random.choice(ESLOGANES)  # uno solo por mensaje, igual en los reintentos
    errores, asunto, cuerpo, intento = [], "", "", 0
    for intento in range(1, MAX_INTENTOS + 1):
        data = generate_json(_prompt(cliente, conocimiento, canal, errores, eslogan), temperature=0.5)
        if not isinstance(data, dict):
            errores = ["La respuesta no fue un JSON válido."]
            continue
        asunto = str(data.get("asunto") or "").strip()
        cuerpo = str(data.get("cuerpo") or "").strip().strip('"')
        errores = validacion.validar(cuerpo, asunto, canal, cliente, conocimiento)
        if not errores:
            break

    if not cuerpo:
        return {"estado_proceso": "omitido", "motivo": "el modelo no produjo texto utilizable"}

    estado = "borrador" if not errores else "requiere_revision"
    cuerpo_final = f"{cuerpo}\n\n{PIE[canal]}"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO public.mensajes
                (clave_cliente, producto, canal, asunto, cuerpo, estado, errores_validacion,
                 modelo, version_prompt, intentos, creado_por)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id_mensaje""",
                (clave, producto, canal, asunto if canal == "correo" else None, cuerpo_final, estado,
                 Json(errores) if errores else None, MODEL, VERSION_PROMPT, intento, usuario))
            inserted = cur.fetchone()
            if inserted is None:
                conn.rollback()
                return {"estado_proceso": "omitido", "motivo": "no se pudo guardar el mensaje"}
            nuevo = inserted[0]
        conn.commit()
    finally:
        conn.close()
    return {"estado_proceso": "generado", "id": nuevo, "estado": estado, "errores": errores}


# ------------------------------------------------------------------ ciclo de vida
def obtener(id_mensaje):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT m.id_mensaje, m.clave_cliente, c.nombre, m.canal, m.producto, m.asunto,
                                  m.cuerpo, m.estado, m.errores_validacion, m.creado_por
                           FROM public.mensajes m
                           LEFT JOIN public.clientes_segmentados c USING (clave_cliente)
                           WHERE m.id_mensaje = %s""", (id_mensaje,))
            row = cur.fetchone()
            columns_info = cur.description
            if row is None or columns_info is None:
                return None
            cols = [d[0] for d in columns_info]
            return dict(zip(cols, row))
    finally:
        conn.close()


def listar(estado=None, limite=20):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT m.id_mensaje, c.nombre, m.canal, m.estado, m.producto, m.fecha_creacion
                           FROM public.mensajes m
                           LEFT JOIN public.clientes_segmentados c USING (clave_cliente)
                           WHERE (%s IS NULL OR m.estado = %s)
                           ORDER BY m.id_mensaje DESC LIMIT %s""", (estado, estado, limite))
            return cur.fetchall()
    finally:
        conn.close()


def cambiar_estado(id_mensaje, nuevo, usuario):
    m = obtener(id_mensaje)
    if not m:
        return False, f"No existe el mensaje {id_mensaje}."
    if nuevo not in TRANSICIONES.get(m["estado"], set()):
        return False, f"No se puede pasar de '{m['estado']}' a '{nuevo}'."
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE public.mensajes SET estado = %s, revisado_por = %s, fecha_estado = now()
                           WHERE id_mensaje = %s""", (nuevo, usuario, id_mensaje))
        conn.commit()
    finally:
        conn.close()
    return True, f"Mensaje {id_mensaje}: {m['estado']} -> {nuevo}."


def formatear(m):
    cab = f"#{m['id_mensaje']} | {m['nombre']} | {m['canal']} | {m['producto']} | estado: {m['estado']}"
    partes = [cab]
    if m.get("asunto"):
        partes.append(f"Asunto: {m['asunto']}")
    partes.append(m["cuerpo"])
    if m.get("errores_validacion"):
        partes.append("⚠ No pasó la validación:\n  - " + "\n  - ".join(m["errores_validacion"]))
    return "\n".join(partes)
