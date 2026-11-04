"""Crea una clave de AI Gateway y la guarda en Vercel. No imprime secretos."""
import json
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ENV = os.environ.copy()
ENV["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
ENV.pop("VERCEL_TOKEN", None)


NPX = Path(
    r"C:\Users\daniela.alvarez\AppData\Local\Microsoft\WinGet\Packages"
    r"\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe"
    r"\node-v24.20.0-win-x64\npx.cmd"
)


def vercel(*args, input_text=None):
    cmd = ["cmd", "/c", str(NPX), "--yes", "vercel@latest", *args]
    r = subprocess.run(
        cmd,
        cwd=RAIZ,
        env=ENV,
        input=input_text,
        capture_output=True,
        text=True,
    )
    return r


def extraer_json(texto):
    texto = texto.strip()
    if not texto:
        return None
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    i, j = texto.find("{"), texto.rfind("}")
    if i >= 0 and j > i:
        try:
            return json.loads(texto[i : j + 1])
        except json.JSONDecodeError:
            return None
    return None


def claves_json(obj, prefijo=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            ruta = f"{prefijo}.{k}" if prefijo else k
            yield ruta
            yield from claves_json(v, ruta)
    elif isinstance(obj, list) and obj:
        yield from claves_json(obj[0], prefijo + "[]")


def clave_de(payload):
    if not isinstance(payload, dict):
        return None
    candidatos = []

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k.lower() in {"key", "apikey", "api_key", "token", "secret", "value", "plaintext"} and isinstance(v, str) and len(v) > 12:
                    candidatos.append(v)
                else:
                    walk(v)
        elif isinstance(obj, list):
            for x in obj:
                walk(x)

    walk(payload)
    return candidatos[0] if candidatos else None


def main():
    create = vercel(
        "ai-gateway", "api-keys", "create",
        "--name", "motor-perfilamiento",
        "--amount", "1",
        "--yes", "--json",
    )
    payload = extraer_json(create.stdout) or extraer_json(create.stderr)
    clave = clave_de(payload or {})
    if not clave:
        # Token Pass (créditos de Vercel) por si el presupuesto de 1 USD pide billing
        create = vercel(
            "ai-gateway", "api-keys", "create",
            "--name", "motor-perfilamiento",
            "--token-pass",
            "--yes", "--json",
        )
        payload = extraer_json(create.stdout) or extraer_json(create.stderr)
        clave = clave_de(payload or {})
    if not clave:
        print("create_code", create.returncode)
        print("json_campos", list(claves_json(payload))[:40] if payload else [])
        err = (create.stderr or create.stdout or "")[:400].replace("\n", " ")
        if any(x in err.lower() for x in ("postgresql://", "sk-", "vck_", "bearer ")):
            print("create_fail [redactado]")
        else:
            print("create_fail", err)
        raise SystemExit(1)
    print("clave_ok", True, "chars", len(clave))

    pares = {
        "LLM_BASE_URL": "https://ai-gateway.vercel.sh/v1",
        "LLM_MODEL": "openai/gpt-4o-mini",
        "LLM_API_KEY": clave,
    }
    for nombre, valor in pares.items():
        tipo = ["--sensitive"] if nombre == "LLM_API_KEY" else ["--no-sensitive"]
        r = vercel(
            "env", "add", nombre,
            "--environment", "production,preview,development",
            "--value", valor,
            "--yes", "--force", *tipo,
        )
        if r.returncode != 0:
            print("env_fail", nombre, (r.stderr or r.stdout or "")[-300].replace("\n", " "))
            raise SystemExit(r.returncode)
        print("env_ok", nombre)
    print("listo")


if __name__ == "__main__":
    sys.exit(main())
