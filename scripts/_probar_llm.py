import json
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

for nombre in ("vercel-llm.env", "vercel-neon.env"):
    p = Path(os.environ["TEMP"]) / nombre
    v = dotenv_values(p) if p.exists() else {}
    print(nombre, "exists", p.exists(), "oidc", bool(v.get("VERCEL_OIDC_TOKEN")), "llm_key_placeholder", (v.get("LLM_API_KEY") or "")[:12])

v = dotenv_values(Path(os.environ["TEMP"]) / "vercel-llm.env")
base = (v.get("LLM_BASE_URL") or "https://ai-gateway.vercel.sh/v1").rstrip("/")
clave = v.get("LLM_API_KEY") or v.get("VERCEL_OIDC_TOKEN") or ""
if clave in ("", "[SENSITIVE]"):
    v2 = dotenv_values(Path(os.environ["TEMP"]) / "vercel-neon.env")
    clave = v2.get("VERCEL_OIDC_TOKEN") or ""
    print("usando_oidc", bool(clave), "chars", len(clave))
model = v.get("LLM_MODEL") or "openai/gpt-4o-mini"
print("model", model, "base", base.endswith("/v1"))

cuerpo = {
    "model": model,
    "messages": [{"role": "user", "content": 'Responde JSON: {"ok": true}'}],
    "temperature": 0,
    "max_tokens": 80,
    "response_format": {"type": "json_object"},
}
req = urllib.request.Request(
    f"{base}/chat/completions",
    data=json.dumps(cuerpo).encode(),
    method="POST",
    headers={"Authorization": f"Bearer {clave}", "Content-Type": "application/json"},
)
ctx = ssl._create_unverified_context()
try:
    with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
        data = json.loads(resp.read().decode())
        content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        print("status", resp.status, "content_len", len(content), "json_ok", "{" in content)
except urllib.error.HTTPError as e:
    print("http", e.code, e.read()[:400].decode("utf-8", "replace"))
