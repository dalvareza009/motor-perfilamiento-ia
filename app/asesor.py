"""Asistente del asesor: pregunta en lenguaje natural -> intención (LLM) -> SQL / borradores (código).
Ejecutar desde la raíz del proyecto:  python -m app.asesor

Comandos directos (sin LLM, para que un cambio de estado nunca dependa de una interpretación):
  /borradores [estado]   /ver ID   /aprobar ID   /descartar ID   /enviado ID
"""
from app import governance, mensajes, segmentos
from app.conocimiento import get_product_knowledge
from app.ollama_client import generate_json, generate_response

ACCIONES = {"contar", "listar", "resumen", "mensaje_segmento", "mensaje_cliente", "mensajes_lote"}
CANALES = {"correo", "whatsapp"}
LIMITE_LOTE = 50


# ------------------------------------------------------------------ interpretación
def interpretar(pregunta):
    """El LLM SOLO traduce la pregunta a una intención estructurada."""
    dims = ", ".join(sorted(segmentos.DIMENSIONES))
    prompt = f"""Convierte la solicitud del asesor en JSON. No respondas la pregunta.
Acciones:
- contar: cuántas personas hay por una dimensión.
- listar: cuáles personas.
- resumen: descripción agregada de un grupo.
- mensaje_segmento: plantilla general de mensaje para un grupo (sin personalizar).
- mensaje_cliente: borrador de mensaje para UNA persona (pon su nombre en "nombre").
- mensajes_lote: un borrador por cada persona de un grupo.
Dimensiones y filtros permitidos: {dims}.
Formato: {{"accion": "...", "agrupar_por": "<dimension o null>", "filtros": {{"<dimension>": "<valor>"}}, "canal": "<correo|whatsapp|null>", "nombre": "<nombre de la persona o null>", "no_soportado": []}}
agrupar_por sirve con contar y con listar. Si no hay filtros, usa {{}}.
"canal" solo si el asesor lo menciona (correo/email o whatsapp); si no, null.
IMPORTANTE: las dimensiones disponibles son solo las listadas. Si la solicitud pide un dato que NO está
(hijos, salario, estado civil...), NO lo asignes a otra dimensión: escríbelo en "no_soportado".
tiene_universidad significa solo "tiene una universidad registrada".
tiene_correo / tiene_celular significan "tiene un correo / celular válido registrado".
Cuando el valor de un filtro es sí/no, usa "si" o "no".
Pon cada dato en su dimensión: una universidad (ej. EAFIT) va en "universidad"; una ocupación en
"profesion"; una ciudad en "ciudad"; un producto en "producto_interes".
Ejemplos:
"clientes de EAFIT en Medellín" -> {{"accion":"listar","agrupar_por":null,"filtros":{{"universidad":"EAFIT","ciudad":"Medellín"}},"canal":null,"nombre":null,"no_soportado":[]}}
"hazme un mensaje de whatsapp para Ana Gómez" -> {{"accion":"mensaje_cliente","agrupar_por":null,"filtros":{{}},"canal":"whatsapp","nombre":"Ana Gómez","no_soportado":[]}}
"mensajes por correo para los de seguro educativo" -> {{"accion":"mensajes_lote","agrupar_por":null,"filtros":{{"producto_interes":"seguro educativo"}},"canal":"correo","nombre":null,"no_soportado":[]}}

Solicitud: {pregunta}"""
    return generate_json(prompt)


def sanear(intencion):
    """Valida lo que devolvió el LLM contra listas blancas (el LLM no es de fiar)."""
    if not isinstance(intencion, dict) or intencion.get("accion") not in ACCIONES:
        return None
    filtros = {}
    descartados = [str(x) for x in (intencion.get("no_soportado") or [])]
    for k, v in (intencion.get("filtros") or {}).items():
        if k in segmentos.DIMENSIONES and isinstance(v, (str, int, bool)):
            filtros[k] = v
        else:
            descartados.append(str(k))
    agrupar = intencion.get("agrupar_por")
    if agrupar not in segmentos.DIMENSIONES:
        agrupar = None
    canal = str(intencion.get("canal") or "").lower().replace("email", "correo")
    nombre = intencion.get("nombre")
    return {"accion": intencion["accion"], "agrupar_por": agrupar, "filtros": filtros,
            "canal": canal if canal in CANALES else None,
            "nombre": nombre.strip() if isinstance(nombre, str) and nombre.strip() else None,
            "no_soportado": list(dict.fromkeys(descartados))}


# ------------------------------------------------------------------ plantilla por segmento (sin personalizar)
TERMINOS_PROHIBIDOS = ["salario", "sueldo", "ingresos", "base de datos", "segmento", "score",
                       "ideal para", "perfecto para", "por ser"]


def validar_mensaje(texto):
    errores = []
    if len(texto.split()) > 60:
        errores.append("Excede 60 palabras.")
    low = texto.lower()
    errores += [f"Término no permitido: '{t}'" for t in TERMINOS_PROHIBIDOS if t in low]
    return errores


def mensaje_segmento(filtros):
    resumen = segmentos.resumen_segmento(filtros)
    producto = filtros.get("producto_interes")
    if not producto and resumen["top_producto_interes"]:
        producto = resumen["top_producto_interes"][0][0]
    conocimiento = get_product_knowledge(producto) if producto else "Sin producto definido."

    prompt = f"""Redacta una plantilla de mensaje comercial para un grupo de clientes de una aseguradora.
HECHOS DEL GRUPO (únicos permitidos): {resumen}
PRODUCTO: {producto}
INFORMACIÓN DEL PRODUCTO:
{conocimiento}

REGLAS:
- Máximo 50 palabras, tono profesional y cercano.
- Usa {{nombre}} como marcador del nombre del cliente.
- Usa solo la información del producto; no inventes coberturas ni beneficios.
- No supongas situaciones personales (hijos, estado civil, necesidades) que no estén en los hechos.
- No menciones segmentos, perfiles, cifras del grupo ni salario.
- Devuelve solo el mensaje."""
    texto = ""
    errores = []
    for _ in range(3):
        texto = generate_response(prompt, temperature=0.3)
        errores = validar_mensaje(texto)
        if not errores:
            return texto, resumen, []
    return texto, resumen, errores


# ------------------------------------------------------------------ acciones
def _contar(intencion, usuario, rol):
    dim = intencion["agrupar_por"] or "segmento"
    todas = segmentos.contar_por(dim, intencion["filtros"])
    visibles = governance.aplicar_k_anonimato(todas, rol)
    ocultos = len(todas) - len(visibles)
    governance.registrar(usuario, rol, "contar", intencion, len(visibles))
    total = sum(n for _, n in todas)
    salida = [f"Clientes por {dim} (total {total}):"]
    salida += [f"  {v}: {n}" for v, n in visibles]
    if ocultos:
        salida.append(f"  ({ocultos} grupo(s) con menos de {governance.K_MIN} personas "
                      f"ocultos por privacidad para el rol {rol})")
    return "\n".join(salida)


def _listar(intencion, usuario, rol):
    filtros = intencion["filtros"]
    rows = segmentos.listar(filtros, governance.LIMITE_LISTADO)
    governance.registrar(usuario, rol, "listar", intencion, len(rows))
    if not rows:
        return "Sin resultados. Diagnóstico por filtro:\n" + segmentos.diagnostico(filtros)
    fmt = lambda r: (f"  {r['nombre']} | {r['genero']} | {r['edad']} | {r['ciudad']} | "
                     f"{r['profesion']} | {r['producto_interes']} | "
                     f"{r['correo'] or 'sin correo'} | {r['celular'] or 'sin celular'}")
    dim = intencion["agrupar_por"]
    if dim:
        grupos = {}
        for r in rows:
            grupos.setdefault(str(r.get(dim) if r.get(dim) is not None else "sin_dato"), []).append(r)
        salida = []
        for g, rs in sorted(grupos.items()):
            salida.append(f"{g} ({len(rs)}):")
            salida += [fmt(r) for r in rs]
    else:
        salida = [fmt(r) for r in rows]
    if len(rows) == governance.LIMITE_LISTADO:
        salida.append(f"(mostrando los primeros {governance.LIMITE_LISTADO}; usa 'contar' para el total)")
    return "\n".join(salida)


def _mensaje_cliente(intencion, usuario, rol):
    if not intencion["nombre"]:
        return "¿Para qué cliente? Indica su nombre o su clave."
    if not intencion["canal"]:
        return "¿Por qué canal: correo o WhatsApp?"
    coincidencias = mensajes.buscar_cliente(intencion["nombre"])
    if not coincidencias:
        return f"No encontré clientes que coincidan con '{intencion['nombre']}'."
    if len(coincidencias) > 1:
        lista = "\n".join(f"  {c[0]} | {c[1]} | {c[2]}" for c in coincidencias)
        return f"Hay varios clientes que coinciden. Repite la solicitud usando la clave:\n{lista}"

    cliente = mensajes.obtener_cliente(coincidencias[0][0])
    if cliente is None:
        return "No se pudo cargar la ficha de ese cliente."

    print("Generando borrador (puede tardar unos segundos)...")
    r = mensajes.generar_para_cliente(cliente, intencion["canal"], usuario)
    governance.registrar(usuario, rol, "mensaje_cliente",
                         {**intencion, "clave": cliente["clave_cliente"], "resultado": r["estado_proceso"]},
                         1 if r["estado_proceso"] != "omitido" else 0)
    if r["estado_proceso"] == "omitido":
        return f"No se generó el mensaje: {r['motivo']}."
    aviso = ""
    if r["estado_proceso"] == "existente":
        aviso = (f"Ya existe el borrador #{r['id']} ({r['estado']}) para este cliente y canal. "
                 f"Si quieres uno nuevo, descártalo con /descartar {r['id']}.\n\n")
    return aviso + mensajes.formatear(mensajes.obtener(r["id"])) + \
        f"\n\nAcciones: /aprobar {r['id']}  /descartar {r['id']}"


def _mensajes_lote(intencion, usuario, rol):
    if not intencion["filtros"]:
        return "Para generar en lote indica un grupo (por ejemplo, el producto o la ciudad)."
    if not intencion["canal"]:
        return "¿Por qué canal: correo o WhatsApp?"
    clientes = segmentos.listar(intencion["filtros"], LIMITE_LOTE)
    if not clientes:
        return "Sin clientes en ese grupo. Diagnóstico por filtro:\n" + segmentos.diagnostico(intencion["filtros"])

    generados, existentes, omitidos, revision = [], [], {}, []
    for i, c in enumerate(clientes, 1):
        print(f"  [{i}/{len(clientes)}] {c['nombre']}...")
        r = mensajes.generar_para_cliente(mensajes.obtener_cliente(c["clave_cliente"]),
                                          intencion["canal"], usuario)
        if r["estado_proceso"] == "generado":
            generados.append(r["id"])
            if r["estado"] == "requiere_revision":
                revision.append(r["id"])
        elif r["estado_proceso"] == "existente":
            existentes.append(r["id"])
        else:
            omitidos.setdefault(r["motivo"], []).append(c["nombre"])

    governance.registrar(usuario, rol, "mensajes_lote", intencion, len(generados))
    out = [f"Lote terminado ({len(clientes)} clientes en el grupo):",
           f"  Borradores generados: {len(generados)} {generados}"]
    if revision:
        out.append(f"  Requieren revisión (no pasaron la validación): {revision}")
    if existentes:
        out.append(f"  Ya tenían borrador activo: {existentes}")
    for motivo, nombres in omitidos.items():
        out.append(f"  Omitidos ({motivo}): {len(nombres)}")
    out.append("Revísalos con /borradores y /ver ID.")
    return "\n".join(out)


def ejecutar(pregunta, usuario, rol):
    crudo = interpretar(pregunta)
    intencion = sanear(crudo)
    print(f"[debug] LLM devolvió: {crudo}")
    print(f"[debug] Aplicado tras validar: {intencion}")
    if intencion is None:
        return "No pude interpretar la solicitud. ¿Puedes reformularla?"
    if intencion["no_soportado"]:
        return ("No tengo estos datos disponibles: " + ", ".join(intencion["no_soportado"]) +
                ".\nNo ejecuté la consulta para no devolverte una lista que ignore ese criterio. "
                "Reformula sin ellos o agrega esos campos a la view.")

    accion = intencion["accion"]
    if not governance.autorizar(rol, accion):
        governance.registrar(usuario, rol, accion, intencion, 0, "denegado")
        return f"Tu rol ({rol}) no tiene permiso para '{accion}'."

    if accion == "contar":
        return _contar(intencion, usuario, rol)
    if accion == "listar":
        return _listar(intencion, usuario, rol)
    if accion == "mensaje_cliente":
        return _mensaje_cliente(intencion, usuario, rol)
    if accion == "mensajes_lote":
        return _mensajes_lote(intencion, usuario, rol)
    if accion == "resumen":
        resumen = segmentos.resumen_segmento(intencion["filtros"])
        governance.registrar(usuario, rol, accion, intencion, resumen["total"])
        return str(resumen)

    texto, resumen, errores = mensaje_segmento(intencion["filtros"])
    governance.registrar(usuario, rol, accion, intencion, resumen["total"])
    aviso = f"\n(⚠ no pasó validación: {errores})" if errores else ""
    return f"Plantilla para {resumen['total']} clientes:\n{texto}{aviso}"


# ------------------------------------------------------------------ comandos directos
ESTADO_DE_COMANDO = {"/aprobar": "aprobado", "/descartar": "descartado", "/enviado": "enviado"}


def comando(linea, usuario, rol):
    partes = linea.split()
    cmd, arg = partes[0], (partes[1] if len(partes) > 1 else None)

    if cmd == "/borradores":
        if not governance.autorizar(rol, "ver_mensajes"):
            return f"Tu rol ({rol}) no tiene permiso para ver borradores."
        filas = mensajes.listar(arg)
        governance.registrar(usuario, rol, "ver_mensajes", {"estado": arg}, len(filas))
        if not filas:
            return "No hay mensajes."
        return "\n".join(f"  #{f[0]} | {f[1]} | {f[2]} | {f[3]} | {f[4]}" for f in filas)

    if cmd == "/ver" and arg and arg.isdigit():
        if not governance.autorizar(rol, "ver_mensajes"):
            return f"Tu rol ({rol}) no tiene permiso para ver borradores."
        m = mensajes.obtener(int(arg))
        governance.registrar(usuario, rol, "ver_mensajes", {"id": int(arg)}, 1 if m else 0)
        return mensajes.formatear(m) if m else "No existe ese mensaje."

    if cmd in ESTADO_DE_COMANDO and arg and arg.isdigit():
        if not governance.autorizar(rol, "cambiar_estado"):
            return f"Tu rol ({rol}) no tiene permiso para cambiar estados."
        ok, msg = mensajes.cambiar_estado(int(arg), ESTADO_DE_COMANDO[cmd], usuario)
        governance.registrar(usuario, rol, "cambiar_estado",
                             {"id": int(arg), "nuevo": ESTADO_DE_COMANDO[cmd]}, 1 if ok else 0,
                             "ok" if ok else "denegado")
        return msg

    return "Comando no reconocido. Usa: /borradores [estado] | /ver ID | /aprobar ID | /descartar ID | /enviado ID"


if __name__ == "__main__":
    usuario = input("Usuario: ").strip()
    rol = ""
    while rol not in governance.PERMISOS:
        rol = input(f"Rol ({'/'.join(governance.PERMISOS)}): ").strip().lower()
    print(f"Sesión iniciada como {usuario} con rol {rol.upper()}. (escribe 'salir' para terminar)")
    while True:
        pregunta = input(f"\n[{rol}] {usuario}> ").strip()
        if pregunta in {"", "salir"}:
            break
        print(comando(pregunta, usuario, rol) if pregunta.startswith("/")
              else ejecutar(pregunta, usuario, rol))