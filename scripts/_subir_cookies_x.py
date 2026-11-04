"""Sube COOKIES_X_JSON a Vercel. No imprime el contenido."""
import json
import os
import subprocess
from pathlib import Path

NPX = Path(
    r"C:\Users\daniela.alvarez\AppData\Local\Microsoft\WinGet\Packages"
    r"\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe"
    r"\node-v24.20.0-win-x64\npx.cmd"
)
RAIZ = Path(__file__).resolve().parents[1]
src = Path(r"c:\Users\daniela.alvarez\Downloads\x.com_cookies (2).json")
if not src.exists():
    src = RAIZ / "x_cookies.json"
raw = json.loads(src.read_text(encoding="utf-8"))
texto = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
print("origen", src.name, "chars", len(texto))

env = os.environ.copy()
env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
env.pop("VERCEL_TOKEN", None)
r = subprocess.run(
    ["cmd", "/c", str(NPX), "--yes", "vercel@latest", "env", "add", "COOKIES_X_JSON",
     "--environment", "production,preview,development",
     "--value", texto, "--yes", "--force", "--sensitive"],
    cwd=RAIZ, env=env, capture_output=True, text=True,
)
if r.returncode != 0:
    err = (r.stderr or r.stdout or "")[-400].replace("\n", " ")
    if "auth_token" in err or "ct0" in err:
        print("env_fail [redactado]")
    else:
        print("env_fail", err)
    raise SystemExit(r.returncode)
print("env_ok COOKIES_X_JSON")
