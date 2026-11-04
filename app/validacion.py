"""Validación determinista de borradores. No depende del LLM ni de la base de datos."""
import re
import unicodedata

LIMITE_PALABRAS = {"whatsapp": 70, "correo": 130}
LIMITE_ASUNTO = 10

SALARIO = ["salario", "sueldo", "ingresos", "rango salarial"]
ORIGEN = ["redes sociales", "página web", "referido", "medio de origen"]
INTERNOS = ["base de datos", "perfil", "perfilamiento", "segmento", "score", "puntaje",
            "datos internos", "analizamos tus datos", "analizamos tu información"]
PROMESAS = ["garantiz", "100%", "sin costo", "gratis", "descuento", "promoción",
            "oferta", "aprobado", "mejor precio", "sin riesgo"]
INFERENCIAS = ["ideal para", "perfecto para", "especialmente para", "diseñado para ti",
               "pensado para ti", "hecho para ti", "por ser", "gracias a tu profesión", "como tú"]
# Términos "de promesa" que SÍ son legítimos si el producto realmente los usa (p. ej. "GlobalUniversidad
# Garantizada", "Garantizado – 100% pago de la matrícula"). El resto de PROMESAS se rechaza siempre.
PROMESAS_SI_ESTAN_EN_PRODUCTO = {"garantiz", "100%"}
# Situaciones personales que NO se pueden asumir: solo valen si están en los DATOS DEL CLIENTE
# (no basta con que el producto hable de "hijos": eso no significa que este cliente los tenga).
SUPUESTOS = ["hijo", "hija", "familia", "esposo", "esposa", "pareja", "padre", "madre",
             "bebé", "embaraz", "estudiante", "jubila"]
MARCA = "global seguros"
# Eslogan principal y frases de campaña vigentes de Global Seguros. El
# generador elige uno al azar por mensaje; cualquiera de los tres es válido.
ESLOGANES = (
    "Tu tranquilidad, en un solo lugar",
    "Pensar en grande, es pensar con Global Seguros",
    "Siempre a tu lado en todos los momentos de la vida",
)
INVITACIONES = ("convers", "hablemos", "hablar", "dialog", "agend", "te gustaria", "quisieras",
                "quieres que", "podemos revisar", "lo revisamos", "te cuento", "te contamos")
# Palabras genéricas que no identifican a una institución concreta.
GENERICAS = {"universidad", "university", "colegio", "institucion", "instituto", "de", "la", "el",
             "en", "at", "the", "y", "del", "estudiante", "student", "ingenieria", "sistemas"}


def _n(texto):
    """Minúsculas y sin tildes, para comparar."""
    t = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def validar(cuerpo, asunto, canal, cliente, conocimiento):
    errores = []
    cuerpo, asunto = (cuerpo or "").strip(), (asunto or "").strip()
    if not cuerpo:
        return ["El mensaje está vacío."]

    texto = _n(f"{asunto} {cuerpo}")

    palabras = len(cuerpo.split())
    if palabras > LIMITE_PALABRAS[canal]:
        errores.append(f"Tiene {palabras} palabras; el máximo para {canal} es {LIMITE_PALABRAS[canal]}.")

    if canal == "correo":
        if not asunto:
            errores.append("Falta el asunto.")
        elif len(asunto.split()) > LIMITE_ASUNTO:
            errores.append(f"El asunto supera {LIMITE_ASUNTO} palabras.")

    producto_n = _n(conocimiento)
    for etiqueta, lista in (("información salarial", SALARIO), ("el medio de origen", ORIGEN),
                            ("información interna", INTERNOS), ("una promesa no respaldada", PROMESAS),
                            ("una inferencia no respaldada", INFERENCIAS)):
        for t in lista:
            if _n(t) in texto and not (lista is PROMESAS and t in PROMESAS_SI_ESTAN_EN_PRODUCTO
                                       and _n(t) in producto_n):
                errores.append(f"Menciona {etiqueta}: '{t}'.")

    datos_cliente = _n(" ".join(str(v) for v in cliente.values() if v))
    for t in SUPUESTOS:
        if _n(t) in texto and _n(t) not in datos_cliente:
            errores.append(f"Asume una situación que no está en los datos del cliente: '{t}'.")

    for n in re.findall(r"\d+", texto):
        if n not in conocimiento:
            errores.append(f"Incluye la cifra '{n}', que no está en la base de conocimiento.")

    if re.search(r"[\[\{][^\]\}]*[\]\}]", f"{asunto} {cuerpo}"):
        errores.append("Contiene marcadores sin reemplazar ([...] o {...}).")

    nombre = (cliente.get("nombre") or "").split()
    if nombre and _n(nombre[0]) not in _n(cuerpo):
        errores.append("No usa el nombre del cliente.")

    # Huella de marca: sin nombrar a Global Seguros el mensaje no es de la compañía,
    # y debe cerrar con alguno de sus eslóganes oficiales.
    if MARCA not in texto:
        errores.append("No incluye la huella de marca de Global Seguros.")
    if not any(_n(e) in texto for e in ESLOGANES):
        errores.append("No cierra con ninguno de los eslóganes de Global Seguros.")

    # Cierre comercial: el mensaje debe invitar a conversar con un asesor.
    if not any(inv in texto for inv in INVITACIONES):
        errores.append("No cierra invitando a conversar con un asesor.")

    # Privacidad: nombrar la universidad, la empresa o la ciudad suena invasivo.
    # Solo se permite la condición general (estudiante, persona que trabaja...).
    for campo in ("universidad", "empresa", "empleador", "ciudad"):
        valor = _n(cliente.get(campo) or "")
        for token in re.findall(r"[a-z0-9]+", valor):
            if len(token) >= 3 and token not in GENERICAS and token in texto:
                errores.append(f"Menciona un dato concreto e invasivo ({campo}: '{token}').")
                break

    return list(dict.fromkeys(errores))