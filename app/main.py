try:
    from app.database import get_connection
    from app.ollama_client import generate_response
except ImportError:          # ejecutado como script desde app/:  python main.py
    from database import get_connection
    from ollama_client import generate_response
import json

def get_client(client_id):
    """
    Consulta un cliente específico desde PostgreSQL.
    """

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT
                id_registro,
                nombre_limpio,
                genero,
                edad,
                ciudad,
                profesion,
                universidad,
                producto_interes
            FROM public.clientes_limpios
            WHERE id_registro = %s;
        """, (client_id,))

        row = cursor.fetchone()

        if not row:
            return None

        columns_info = cursor.description
        if columns_info is None:
            return None

        columns = [description[0] for description in columns_info]

        return dict(zip(columns, row))

    finally:
        cursor.close()
        connection.close()

def get_consolidated_client(clave_cliente):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT
                clave_cliente,
                nombre,
                genero,
                edad,
                ciudad,
                profesion,
                universidad,
                producto_interes
            FROM public.clientes_consolidados
            WHERE clave_cliente = %s;
        """, (clave_cliente,))

        row = cursor.fetchone()

        if not row:
            return None

        columns_info = cursor.description
        if columns_info is None:
            return None

        columns = [description[0] for description in columns_info]

        return dict(zip(columns, row))

    finally:
        cursor.close()
        connection.close()

def build_prompt(client, knowledge):
    return f"""
Eres un asistente encargado de generar mensajes personalizados
para clientes de una compañía de seguros.

DATOS DEL CLIENTE:
Nombre: {client['nombre_limpio']}
Edad: {client['edad']}
Ciudad: {client['ciudad']}
Profesión: {client['profesion']}
Universidad: {client['universidad']}
Producto de interés: {client['producto_interes']}

INFORMACIÓN DEL PRODUCTO:
{knowledge}

REGLAS:
- Escribe únicamente el mensaje final.
- Máximo 40 palabras.
- Usa un tono profesional y cercano.
- Personaliza el mensaje utilizando únicamente datos explícitos del cliente.
- Utiliza únicamente la información proporcionada.
- No establezcas relaciones entre datos del cliente y beneficios del producto que no estén explícitamente indicadas.
- No asumas que el producto aplica a una situación específica del cliente.
- No inventes beneficios, coberturas ni características.
- No menciones salario.
- No menciones el medio de origen.
- No menciones información interna.
- No expliques tu razonamiento.
"""

def build_profile_prompt(client):
    return f"""
Eres un asistente encargado de construir perfiles de clientes
para una compañía de seguros.

DATOS DEL CLIENTE:

Nombre: {client['nombre']}
Género: {client['genero']}
Edad: {client['edad']}
Ciudad: {client['ciudad']}
Profesión: {client['profesion']}
Universidad: {client['universidad']}
Producto de interés: {client['producto_interes']}

REGLAS ESTRICTAS:

- Utiliza únicamente los datos proporcionados.
- No inventes información.
- No hagas inferencias.
- No interpretes los datos.
- No agregues información que no aparezca explícitamente.
- Si aparece una universidad, NO significa que la persona sea estudiante.
- Si aparece una profesión, NO agregues años de experiencia, cargo,
  empresa o actividades relacionadas.
- Si aparece una edad, NO infieras etapa de vida, estado civil,
  hijos, necesidades o situación económica.
- Si aparece una ciudad, NO infieras características del cliente.
- No menciones salario.
- No menciones el medio de origen.
- El segmento debe construirse únicamente con características
  explícitas y observables de los datos.
- Las características relevantes deben repetir únicamente información
  explícita de los datos.
- El perfil consolidado debe ser una síntesis de los datos explícitos,
  sin agregar información nueva.
- No utilices expresiones como "estudiante", "padre", "madre",
  "profesional con experiencia", "interesado en proteger a su familia"
  o similares, a menos que aparezcan explícitamente en los datos.
- Devuelve únicamente un JSON válido.
- No incluyas explicaciones fuera del JSON.

FORMATO OBLIGATORIO:

{{
    "segmento": "...",
    "caracteristicas_relevantes": "...",
    "perfil_consolidado": "..."
}}
"""

def save_profile(client, profile):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO public.perfiles (
                id_cliente_consolidado,
                segmento,
                score,
                caracteristicas_relevantes,
                perfil_consolidado,
                fecha_actualizacion
            )
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (id_cliente_consolidado)
            DO UPDATE SET
                segmento = EXCLUDED.segmento,
                score = EXCLUDED.score,
                caracteristicas_relevantes = EXCLUDED.caracteristicas_relevantes,
                perfil_consolidado = EXCLUDED.perfil_consolidado,
                fecha_actualizacion = CURRENT_TIMESTAMP
            RETURNING id_perfil;
        """, (
            client["clave_cliente"],
            profile["segmento"],
            None,
            profile["caracteristicas_relevantes"],
            profile["perfil_consolidado"]
        ))

        inserted = cursor.fetchone()
        if inserted is None:
            connection.rollback()
            raise RuntimeError("El INSERT no devolvió id_perfil.")

        profile_id = inserted[0]
        connection.commit()

        return profile_id

    finally:
        cursor.close()
        connection.close()

def get_saved_profile(profile_id):
    """
    Consulta el perfil que acabamos de guardar.
    """
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT
                id_perfil,
                id_cliente_consolidado,
                segmento,
                score,
                caracteristicas_relevantes,
                perfil_consolidado
            FROM public.perfiles
            WHERE id_perfil = %s;
        """, (profile_id,))

        row = cursor.fetchone()

        if not row:
            return None

        columns_info = cursor.description

        if columns_info is None:
            return None

        columns = [description[0] for description in columns_info]

        return dict(zip(columns, row))

    finally:
        cursor.close()
        connection.close()

def build_message_prompt(client, profile, knowledge):

    return f"""
Eres un asistente encargado de generar mensajes personalizados
para clientes de Global Seguros.

PERFIL DEL CLIENTE:

Nombre: {client['nombre']}
Producto de interés: {client['producto_interes']}

PERFIL CONSOLIDADO:

{profile['perfil_consolidado']}

INFORMACIÓN DEL PRODUCTO:

{knowledge}

REGLAS:

- Escribe únicamente el mensaje final dirigido al cliente.
- Entre 50 y 70 palabras: explica muy resumidamente qué protege o paga el seguro
  y para qué sirve, solo con la información del producto.
- Usa un tono profesional, cercano y natural, con la huella de Global Seguros:
  preséntate como Global Seguros y cierra con uno de sus eslóganes: «Tu
  tranquilidad, en un solo lugar», «Pensar en grande, es pensar con Global
  Seguros» o «Siempre a tu lado en todos los momentos de la vida».
- Cierra invitando a conversar con un asesor de Global Seguros.
- Utiliza el nombre del cliente cuando sea apropiado.
- Personaliza solo con la condición general del cliente (estudiante, persona que
  trabaja, persona independiente...). Aunque conozcas el dato concreto, NUNCA
  menciones universidades, colegios, empresas, empleadores, instituciones, cargos
  detallados ni ciudad: suena invasivo.
- Utiliza únicamente información contenida en el conocimiento del producto.
- No inventes beneficios, coberturas ni características.
- No establezcas relaciones entre características del cliente y beneficios
  del producto que no estén explícitamente indicadas.
- No asumas necesidades específicas del cliente.
- No menciones salario.
- No menciones el medio de origen.
- No menciones información interna como perfil, segmento, score,
  características relevantes o bases de datos.
- No expliques tu razonamiento.
- Devuelve únicamente el mensaje que recibirá el cliente.
"""

def get_product_knowledge(product):
    conn = get_connection()

    query = """
        SELECT categoria, titulo, contenido
        FROM public.conocimiento
        WHERE LOWER(producto) = LOWER(%s)
          AND activo = true
        ORDER BY id_conocimiento;
    """

    with conn.cursor() as cursor:
        cursor.execute(query, (product,))
        rows = cursor.fetchall()

    conn.close()

    return rows

def format_knowledge(rows):
    if not rows:
        return "No hay información disponible sobre el producto."

    knowledge = []

    for categoria, titulo, contenido in rows:
        knowledge.append(
            f"- {categoria}: {titulo}\n"
            f"  {contenido}"
        )

    return "\n".join(knowledge)

def validate_message(message, client, knowledge):
    """
    Valida que el mensaje generado por Qwen cumpla
    las reglas básicas del proyecto.
    """

    errors = []

    # --------------------------------------------------
    # 1. Validar que exista un mensaje
    # --------------------------------------------------
    if not message or not message.strip():
        errors.append("El mensaje está vacío.")
        return False, errors

    message_clean = message.strip()

    # --------------------------------------------------
    # 2. Máximo 40 palabras
    # --------------------------------------------------
    word_count = len(message_clean.split())

    if word_count > 40:
        errors.append(
            f"El mensaje tiene {word_count} palabras. "
            f"El máximo permitido es 40."
        )

    # --------------------------------------------------
    # 3. No mencionar salario
    # --------------------------------------------------
    forbidden_salary_terms = [
        "salario",
        "sueldo",
        "ingresos",
        "rango salarial",
        "millones"
    ]

    message_lower = message_clean.lower()

    for term in forbidden_salary_terms:
        if term in message_lower:
            errors.append(
                f"El mensaje menciona información salarial: '{term}'."
            )

    # --------------------------------------------------
    # 4. No mencionar medio de origen
    # --------------------------------------------------
    forbidden_origin_terms = [
        "redes sociales",
        "página web",
        "referido",
        "comercial",
        "digital",
        "medio de origen"
    ]

    for term in forbidden_origin_terms:
        if term in message_lower:
            errors.append(
                f"El mensaje menciona el medio de origen: '{term}'."
            )

    # --------------------------------------------------
    # 5. No mencionar información interna
    # --------------------------------------------------
    forbidden_internal_terms = [
        "base de datos",
        "perfil",
        "perfilamiento",
        "segmento",
        "score",
        "puntaje",
        "datos internos",
        "analizamos tus datos",
        "analizamos tu información"
    ]

    for term in forbidden_internal_terms:
        if term in message_lower:
            errors.append(
                f"El mensaje menciona información interna: '{term}'."
            )

    # --------------------------------------------------
    # 6. Evitar relaciones inventadas
    # --------------------------------------------------
    forbidden_inferences = [
        "ideal para",
        "perfecto para",
        "especialmente para",
        "diseñado para ti",
        "pensado para ti",
        "hecho para ti",
        "por ser",
        "gracias a tu profesión",
        "como tú",
        "para ingenieros",
        "para ingenieras",
        "para profesionales como tú"
    ]

    for phrase in forbidden_inferences:
        if phrase in message_lower:
            errors.append(
                f"El mensaje contiene una posible inferencia no respaldada: "
                f"'{phrase}'."
            )

    # --------------------------------------------------
    # 7. Validar que mencione al cliente
    # --------------------------------------------------
    client_name = client.get("nombre", "").strip()

    if client_name:
        first_name = client_name.split()[0].lower()

        if first_name not in message_lower:
            errors.append(
                "El mensaje no utiliza el nombre del cliente."
            )

    # --------------------------------------------------
    # RESULTADO
    # --------------------------------------------------
    if errors:
        return False, errors

    return True, []

def get_profile(clave_cliente):

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT
                id_perfil,
                id_cliente_consolidado,
                segmento,
                score,
                caracteristicas_relevantes,
                perfil_consolidado
            FROM public.perfiles
            WHERE id_cliente_consolidado = %s;
        """, (clave_cliente,))

        row = cursor.fetchone()

        if not row:
            return None

        columns_info = cursor.description

        if columns_info is None:
            return None

        columns = [
            description[0]
            for description in columns_info
        ]

        return dict(zip(columns, row))

    finally:
        cursor.close()
        connection.close()

def main():

    clave_cliente = input("Ingrese la clave del cliente: ").strip()
    
    client = get_consolidated_client(clave_cliente)

    if client is None:
        print("No se encontró el cliente.")
        return

    print("\n============================================================")
    print("1. CLIENTE ENCONTRADO")
    print("============================================================")

    print(client)

    prompt = build_profile_prompt(client)

    print("\n============================================================")
    print("2. GENERANDO PERFIL CON QWEN...")
    print("============================================================")

    profile_response = generate_response(prompt)
    
    print("\nRESPUESTA DE QWEN:")
    print(profile_response)

    try:
        profile = json.loads(profile_response)
    except json.JSONDecodeError:
        print("\nERROR: Qwen no devolvió un JSON válido.")
        return

    profile_id = save_profile(client, profile)

    print("\n============================================================")
    print("3. PERFIL GUARDADO")
    print("============================================================")
    print(f"ID del perfil: {profile_id}")

    # ---------------------------------------------------------
    # 4. CONSULTAR PERFIL GUARDADO
    # ---------------------------------------------------------

    saved_profile = get_saved_profile(profile_id)

    if saved_profile is None:
        print("\nERROR: No se pudo recuperar el perfil guardado.")
        return

    print("\n============================================================")
    print("4. PERFIL RECUPERADO")
    print("============================================================")
    print(saved_profile)

    # ---------------------------------------------------------
    # 5. CONSULTAR CONOCIMIENTO DEL PRODUCTO
    # ---------------------------------------------------------

    knowledge_rows = get_product_knowledge(
        client["producto_interes"]
    )

    knowledge = format_knowledge(knowledge_rows)

    print("\n============================================================")
    print("5. CONOCIMIENTO DEL PRODUCTO")
    print("============================================================")
    print(knowledge)

    # ---------------------------------------------------------
    # 6. GENERAR MENSAJE PERSONALIZADO
    # ---------------------------------------------------------

    message_prompt = build_message_prompt(
        client,
        saved_profile,
        knowledge
    )

    print("\n============================================================")
    print("6. GENERANDO MENSAJE CON QWEN...")
    print("============================================================")

    message_response = generate_response(message_prompt)

    print("\n============================================================")
    print("MENSAJE GENERADO")
    print("============================================================")
    print(message_response)
    print("============================================================")

    valid, errors = validate_message(
        message_response,
        client,
        knowledge
    )
    print("\nDEBUG RESPONSE:")
    print(repr(message_response))
    print("PALABRAS:", len(message_response.strip().split()))

    print("\n============================================================")
    print("7. VALIDACIÓN DEL MENSAJE")
    print("============================================================")

    if valid:
        print("✓ MENSAJE APROBADO")
    else:
        print("✗ MENSAJE RECHAZADO")

        for error in errors:
            print(f"- {error}")

if __name__ == "__main__":
    main()