"""Índice vectorial del conocimiento aprobado.

  python -m app.vectorizar
"""
import hashlib

from app import embeddings
from app.database import get_connection


def _texto(categoria, titulo, contenido):
    return f"{categoria}: {titulo}\n{contenido}"


def _hash(contenido, guardado):
    if guardado:
        return guardado
    return hashlib.sha256((contenido or "").encode("utf-8")).hexdigest()


def _tabla_existe(cur):
    cur.execute("""SELECT EXISTS (
                     SELECT 1 FROM information_schema.tables
                     WHERE table_schema = 'public' AND table_name = 'conocimiento_embeddings')""")
    return cur.fetchone()[0]


def _asegurar_tabla(cur, dim):
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS public.conocimiento_embeddings (
                      id_conocimiento integer PRIMARY KEY
                        REFERENCES public.conocimiento (id_conocimiento) ON DELETE CASCADE,
                      embedding vector({int(dim)}),
                      hash_contenido text,
                      modelo text)""")


def _pendientes(cur, modelo):
    if not _tabla_existe(cur):
        cur.execute("""SELECT id_conocimiento, categoria, titulo, contenido, hash_contenido
                       FROM public.conocimiento WHERE activo ORDER BY id_conocimiento""")
        return [(i, c, t, x, _hash(x, h)) for i, c, t, x, h in cur.fetchall()]

    cur.execute("""SELECT c.id_conocimiento, c.categoria, c.titulo, c.contenido, c.hash_contenido,
                          e.hash_contenido, e.modelo
                   FROM public.conocimiento c
                   LEFT JOIN public.conocimiento_embeddings e USING (id_conocimiento)
                   WHERE c.activo ORDER BY c.id_conocimiento""")
    pendientes = []
    for i, c, t, x, h, eh, em in cur.fetchall():
        hh = _hash(x, h)
        if eh != hh or em != modelo:
            pendientes.append((i, c, t, x, hh))
    return pendientes


def _borrar_inactivos(cur):
    cur.execute("""DELETE FROM public.conocimiento_embeddings e
                   WHERE NOT EXISTS (
                     SELECT 1 FROM public.conocimiento c
                     WHERE c.id_conocimiento = e.id_conocimiento AND c.activo)""")


def _embed_lotes(textos, lote):
    vectores = []
    for i in range(0, len(textos), lote):
        vectores.extend(embeddings.embed(textos[i:i + lote]))
    return vectores


def sincronizar(lote=16):
    """Vectoriza lo activo que cambió y quita lo desactivado. -> {'vectorizados': n}."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            existe = _tabla_existe(cur)
            pendientes = _pendientes(cur, embeddings.EMBED_MODEL)
            if pendientes:
                vectores = _embed_lotes([_texto(c, t, x) for _, c, t, x, _ in pendientes], lote)
                _asegurar_tabla(cur, len(vectores[0]))
                for (idc, _, _, _, h), vec in zip(pendientes, vectores):
                    cur.execute("""INSERT INTO public.conocimiento_embeddings
                                   (id_conocimiento, embedding, hash_contenido, modelo)
                                   VALUES (%s, %s::vector, %s, %s)
                                   ON CONFLICT (id_conocimiento) DO UPDATE
                                   SET embedding = EXCLUDED.embedding,
                                       hash_contenido = EXCLUDED.hash_contenido,
                                       modelo = EXCLUDED.modelo""",
                                (idc, embeddings.a_literal(vec), h, embeddings.EMBED_MODEL))
            if existe or pendientes:
                _borrar_inactivos(cur)
        conn.commit()
    finally:
        conn.close()
    return {"vectorizados": len(pendientes)}


def main():
    r = sincronizar()
    print(f"Índice vectorial actualizado ({r['vectorizados']} fragmentos vectorizados).")


if __name__ == "__main__":
    main()
