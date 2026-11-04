"""Sube el proyecto a Vercel con las cookies de sesión (sin token CLI)."""
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
COOKIES = Path(r"c:\Users\daniela.alvarez\Downloads\vercel.com_cookies.json")
SKIP_DIR = {
    ".venv", ".git", ".cursor", ".vercel", "__pycache__", "agent-transcripts",
    "chrome_linkedin_profile", "chrome_facebook_profile", "chrome_instagram_profile",
    "chrome_x_profile", "node_modules",
}
SKIP_FILE = {
    ".env", "x_cookies.json", "linkedin_cookies.json", "facebook_cookies.json",
    "instagram_cookies.json", "_vercel_token.py",
}
SKIP_SUF = {".pyc", ".csv", ".pdb"}
MAX_BYTES = 8 * 1024 * 1024


def cookie_header():
    raw = json.loads(COOKIES.read_text(encoding="utf-8"))
    cookies = raw.get("cookies", raw) if isinstance(raw, dict) else raw
    return "; ".join(
        f"{c['name']}={c['value']}"
        for c in cookies if isinstance(c, dict) and c.get("name") and "value" in c
    )


def api(method, url, data=None, extra=None, raw=False):
    headers = {
        "Cookie": cookie_header(),
        "User-Agent": "Mozilla/5.0 motor-perfilamiento",
        "Accept": "application/json",
    }
    if extra:
        headers.update(extra)
    body = data
    if isinstance(data, (dict, list)):
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = resp.read()
            if raw:
                return resp.status, payload
            if not payload:
                return resp.status, {}
            return resp.status, json.loads(payload.decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode(errors="replace")
        try:
            parsed = json.loads(err)
        except json.JSONDecodeError:
            parsed = err[:400]
        return e.code, parsed


def listar_archivos():
    archivos = []
    for path in RAIZ.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(RAIZ)
        if any(p in SKIP_DIR for p in rel.parts):
            continue
        if rel.name in SKIP_FILE or rel.suffix.lower() in SKIP_SUF:
            continue
        if rel.name.startswith("._"):
            continue
        size = path.stat().st_size
        if size > MAX_BYTES:
            print("omitido grande", rel, size)
            continue
        sha = hashlib.sha1(path.read_bytes()).hexdigest()
        archivos.append((rel.as_posix(), path, sha, size))
    return archivos


def main():
    status, user = api("GET", "https://api.vercel.com/v2/user")
    if status != 200:
        raise SystemExit(f"sesion vercel no valida: {status} {user}")
    username = user["user"]["username"]
    team = user["user"].get("defaultTeamId")
    print("sesion ok", username, "team", team)
    qs = f"?teamId={team}" if team else ""

    archivos = listar_archivos()
    print("archivos", len(archivos), "bytes", sum(a[3] for a in archivos))

    for i, (rel, path, sha, size) in enumerate(archivos, 1):
        st, body = api(
            "POST", f"https://api.vercel.com/v2/files{qs}",
            data=path.read_bytes(),
            extra={"x-vercel-digest": sha, "Content-Type": "application/octet-stream"},
            raw=True,
        )
        if st not in (200, 201, 409):
            print("upload fail", rel, st, body[:200] if isinstance(body, (bytes, str)) else body)
            raise SystemExit(1)
        if i % 25 == 0 or i == len(archivos):
            print("subidos", i, "/", len(archivos))

    payload = {
        "name": "motor-perfilamiento-ia",
        "project": "motor-perfilamiento-ia",
        "target": "preview",
        "files": [{"file": rel, "sha": sha, "size": size} for rel, _, sha, size in archivos],
        "projectSettings": {"framework": "container"},
        "env": {
            "DEMO_CLAVE": "jefe-prueba-2026",
            "SESION_SECRETA": "jefe-prueba-2026",
            "SCRAPE_HEADLESS": "1",
            "SCRAPE_MANUAL_LOGIN": "0",
        },
    }
    st, dep = api("POST", f"https://api.vercel.com/v13/deployments{qs}", payload)
    print("deploy status", st)
    if st not in (200, 201):
        print(dep)
        raise SystemExit(1)
    url = dep.get("url") or dep.get("readyState")
    print("id", dep.get("id"))
    print("url", f"https://{dep['url']}" if dep.get("url") and not str(dep.get("url")).startswith("http") else dep.get("url"))
    print("inspector", dep.get("inspectorUrl"))
    print("ready", dep.get("readyState"))

    dep_id = dep.get("id")
    for _ in range(90):
        time.sleep(8)
        st, now = api("GET", f"https://api.vercel.com/v13/deployments/{dep_id}{qs}")
        state = (now or {}).get("readyState") if isinstance(now, dict) else None
        print("estado", state)
        if state in ("READY", "ERROR", "CANCELED"):
            if isinstance(now, dict):
                alias = now.get("alias") or now.get("url")
                print("final", state, alias)
                if now.get("url"):
                    print("https://" + now["url"] if not str(now["url"]).startswith("http") else now["url"])
            break


if __name__ == "__main__":
    os.chdir(RAIZ)
    main()
