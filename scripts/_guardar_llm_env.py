"""Lee la clave de AI Gateway ya creada y la sube a Vercel. No imprime secretos."""
import os
import re
import subprocess
from pathlib import Path

NPX = Path(
    r"C:\Users\daniela.alvarez\AppData\Local\Microsoft\WinGet\Packages"
    r"\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe"
    r"\node-v24.20.0-win-x64\npx.cmd"
)
RAIZ = Path(__file__).resolve().parents[1]
ENV = os.environ.copy()
ENV["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
ENV.pop("VERCEL_TOKEN", None)

raw = Path(os.environ["TEMP"], "gw-create.txt").read_text(encoding="utf-8", errors="replace")
clave = None
for linea in raw.splitlines():
    s = linea.strip()
    if re.match(r"^(vck_|sk-|gw_)[A-Za-z0-9._\-]+$", s):
        clave = s
        break
if not clave:
    raise SystemExit("no se encontro la clave en la salida")
print("clave_ok", True, "chars", len(clave))

pares = [
    ("LLM_BASE_URL", "https://ai-gateway.vercel.sh/v1", False),
    ("LLM_MODEL", "openai/gpt-4o-mini", False),
    ("LLM_API_KEY", clave, True),
]
for nombre, valor, secreto in pares:
    tipo = "--sensitive" if secreto else "--no-sensitive"
    r = subprocess.run(
        ["cmd", "/c", str(NPX), "--yes", "vercel@latest", "env", "add", nombre,
         "--environment", "production,preview,development",
         "--value", valor, "--yes", "--force", tipo],
        cwd=RAIZ, env=ENV, capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("env_fail", nombre, (r.stderr or r.stdout or "")[-250].replace("\n", " "))
        raise SystemExit(r.returncode)
    print("env_ok", nombre)
print("listo")
