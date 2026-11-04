"""Recuperación de conocimiento de producto.
Con consulta -> búsqueda vectorial (solo los fragmentos relevantes + las reglas de negocio).
Sin consulta, o si pgvector/Ollama no responden -> conocimiento completo (comportamiento anterior)."""
import os

from app import embeddings
from app.database import get_connection

PRIORIDAD = {"regla de negocio": 0, "producto": 1, "cobertura": 2, "beneficio": 3, "pregunta frecuente": 4,
             "clausulado": 5, "exclusion": 5, "exclusión": 5}
MAX_CHARS = 4000
MIN_SIM = float(os.getenv("RAG_MIN_SIM", "0"))   # 0 = sin umbral; súbelo (p. ej. 0.4) tras probar con tus datos


def formatear(fragmentos, max_chars=MAX_CHARS, ordenar=True):
    """-> (texto, títulos usados). Con ordenar=False respeta el orden recibido (por similitud)."""
    frs = (sorted(fragmentos, key=lambda f: PRIORIDAD.get((f["categoria"] or "").lower(), 9))
           if ordenar else list(fragmentos))
    partes, usados, total = [], [], 0
    for f in frs:
        bloque = f"- {f['categoria']}: {f['titulo']}\n  {f['contenido']}"
        if total + len(bloque) > max_chars and partes:
            break
        partes.append(bloque)
        usados.append(f["titulo"])
        total += len(bloque)
    return "\n".join(partes), usados


def _todos(producto):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT categoria, titulo, contenido FROM public.conocimiento
                           WHERE LOWER(producto) = LOWER(%s) AND activo = true
                           ORDER BY id_conocimiento""", (producto,))
            return [{"categoria": c, "titulo": t, "contenido": x} for c, t, x in cur.fetchall()]
    finally:
        conn.close()


def buscar_fragmentos(producto, consulta, k=5):
    """Reglas de negocio del producto (siempre) + los k fragmentos más cercanos a la consulta."""
    vec = embeddings.a_literal(embeddings.embed([consulta])[0])
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            reglas = []
            if producto:
                cur.execute("""SELECT categoria, titulo, contenido FROM public.conocimiento
                               WHERE activo AND LOWER(producto) = LOWER(%s)
                                 AND LOWER(categoria) = 'regla de negocio' ORDER BY id_conocimiento""",
                            (producto,))
                reglas = [{"categoria": c, "titulo": t, "contenido": x} for c, t, x in cur.fetchall()]
            cur.execute("""SELECT c.categoria, c.titulo, c.contenido, 1 - (e.embedding <=> %s::vector) AS sim
                           FROM public.conocimiento c
                           JOIN public.conocimiento_embeddings e USING (id_conocimiento)
                           WHERE c.activo AND LOWER(c.categoria) <> 'regla de negocio'
                             AND (%s::text IS NULL OR LOWER(c.producto) = LOWER(%s))
                           ORDER BY e.embedding <=> %s::vector LIMIT %s""",
                        (vec, producto, producto, vec, k))
            top = [{"categoria": c, "titulo": t, "contenido": x, "similitud": float(s)}
                   for c, t, x, s in cur.fetchall() if float(s) >= MIN_SIM]
    finally:
        conn.close()
    return (reglas + top) if top else []


def recuperar(producto, consulta=None, k=5, max_chars=MAX_CHARS):
    """-> (texto, títulos usados, modo) con modo 'vectorial' o 'completo'."""
    if consulta:
        try:
            frs = buscar_fragmentos(producto, consulta, k)
        except Exception as e:   # sin pgvector, sin tabla, Ollama caído...
            print(f"[rag] búsqueda vectorial no disponible ({type(e).__name__}); uso conocimiento completo.")
            frs = []
        if frs:
            texto, titulos = formatear(frs, max_chars, ordenar=False)
            print(f"[rag] vectorial: {len(titulos)} fragmentos -> {titulos}")
            return texto, titulos, "vectorial"

    frs = _todos(producto) if producto else []
    if not frs:
        return "No hay información disponible sobre el producto.", [], "completo"
    texto, titulos = formatear(frs, max_chars)
    return texto, titulos, "completo"


def get_product_knowledge(producto, consulta=None, k=5, max_chars=MAX_CHARS):
    return recuperar(producto, consulta, k, max_chars)[0]