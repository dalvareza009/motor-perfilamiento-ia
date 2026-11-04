import json
import os
import re

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL = os.getenv("OLLAMA_MODEL") or os.getenv("LLM_MODEL") or "qwen3:4b-instruct"


def _modelo():
    return os.getenv("OLLAMA_MODEL") or os.getenv("LLM_MODEL") or "qwen3:4b-instruct"


def _usa_openai():
    return bool(os.getenv("LLM_BASE_URL"))


def generate_response(prompt, json_mode=False, temperature=0.3, num_predict=1000):
    if _usa_openai():
        return _openai(prompt, json_mode=json_mode, temperature=temperature, num_predict=num_predict)
    payload = {
        "model": _modelo(),
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"num_predict": num_predict, "temperature": temperature},
    }
    if json_mode:
        payload["format"] = "json"

    url = os.getenv("OLLAMA_URL", OLLAMA_URL)
    response = requests.post(url, json=payload, timeout=300)
    response.raise_for_status()
    content = response.json()["message"]["content"]

    if "</think>" in content:
        content = content.split("</think>", 1)[1]
    return content.strip()


def _openai(prompt, json_mode=False, temperature=0.3, num_predict=1000):
    base = os.getenv("LLM_BASE_URL", "").rstrip("/")
    clave = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("VERCEL_OIDC_TOKEN") or ""
    cuerpo = {
        "model": _modelo(),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": num_predict,
    }
    if json_mode:
        cuerpo["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {clave}"} if clave else {}
    response = requests.post(f"{base}/chat/completions", json=cuerpo, headers=headers, timeout=300)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return (content or "").strip()


def generate_json(prompt, retries=2, temperature=0.0):
    """Devuelve un dict o None. Tolera texto o ``` alrededor del JSON."""
    for _ in range(retries + 1):
        raw = generate_response(prompt, json_mode=True, temperature=temperature)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            continue
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
    return None
