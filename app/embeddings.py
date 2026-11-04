"""Embeddings con Ollama y literal de pgvector."""
import os

import requests

OLLAMA_EMBED_URL = os.getenv("OLLAMA_EMBED_URL", "http://localhost:11434/api/embed")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")


def embed(textos):
    """Lista de textos -> lista de vectores."""
    base = (os.getenv("LLM_BASE_URL") or "").rstrip("/")
    if base:
        clave = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("VERCEL_OIDC_TOKEN") or ""
        modelo = os.getenv("EMBED_MODEL", EMBED_MODEL)
        response = requests.post(
            f"{base}/embeddings",
            json={"model": modelo, "input": list(textos)},
            headers={"Authorization": f"Bearer {clave}"} if clave else {},
            timeout=120,
        )
        response.raise_for_status()
        filas = sorted(response.json().get("data") or [], key=lambda x: x.get("index", 0))
        vectores = [f.get("embedding") for f in filas]
    else:
        response = requests.post(
            os.getenv("OLLAMA_EMBED_URL", OLLAMA_EMBED_URL),
            json={"model": os.getenv("EMBED_MODEL", EMBED_MODEL), "input": list(textos)},
            timeout=120,
        )
        response.raise_for_status()
        vectores = response.json().get("embeddings")
    if not vectores or len(vectores) != len(textos):
        raise RuntimeError("El servicio de embeddings no devolvió un vector por cada texto.")
    return vectores


def a_literal(vector):
    """Vector numérico -> literal que acepta pgvector, p. ej. '[0.1,0.2]'."""
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"
