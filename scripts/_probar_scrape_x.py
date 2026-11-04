"""Prueba corta de scraping de X en Vercel. No imprime cookies ni PII."""
import json
import ssl
import time
import urllib.error
import urllib.request

ctx = ssl._create_unverified_context()
BASE = "https://motor-perfilamiento-ia.vercel.app"
URL = "https://x.com/yiosalgo76"


def req(method, path, data=None, token=None, timeout=60):
    headers = {"Accept": "application/json"}
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(BASE + path, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ctx) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        bruto = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(bruto)
        except json.JSONDecodeError:
            parsed = {"detail": bruto[:400]}
        return e.code, parsed


def main():
    st, ses = req("POST", "/api/sesion", {"usuario": "prueba-scrape", "rol": "admin", "clave": "jefe-prueba-2026"})
    if st != 200:
        print("sesion_fail", st, ses)
        raise SystemExit(1)
    token = ses["token"]
    print("sesion_ok", ses.get("rol"))
    print("lanzando scrape", URL, "max_posts=2")
    t0 = time.time()
    st, body = req("POST", "/api/x/actividad", {"url": URL, "max_posts": 2}, token=token, timeout=300)
    print("post_status", st, "s", round(time.time() - t0, 1))
    tarea = body.get("tarea") or body
    print("estado", tarea.get("estado"), "error", (tarea.get("error") or body.get("detail") or "")[:240])
    res = tarea.get("resultado") or {}
    if isinstance(res, dict):
        print("ok", res.get("ok"), "publicaciones", res.get("publicaciones"), "motivo", res.get("motivo"))
        print("recomendaciones", len(res.get("recomendaciones") or []))
        g = res.get("guardado") or {}
        if isinstance(g, dict):
            print("hechos_guardados", g.get("hechos") or g.get("n") or list(g)[:6])
    lineas = tarea.get("lineas") or []
    print("log_lineas", len(lineas))
    for ln in lineas[-12:]:
        s = str(ln)
        if "auth_token" in s or "ct0=" in s:
            print("  [redactado]")
        else:
            print(" ", s[:200])

    tid = tarea.get("id")
    if tid and tarea.get("estado") == "en_curso":
        for i in range(24):
            time.sleep(8)
            st, now = req("GET", f"/api/tareas/{tid}", token=token, timeout=30)
            tnow = now if "estado" in now else (now.get("tarea") or now)
            print("poll", i + 1, tnow.get("estado"), (tnow.get("error") or "")[:160])
            if tnow.get("estado") in ("terminada", "error"):
                lineas = tnow.get("lineas") or []
                for ln in lineas[-8:]:
                    print(" ", str(ln)[:200])
                res = tnow.get("resultado") or {}
                if isinstance(res, dict):
                    print("ok", res.get("ok"), "publicaciones", res.get("publicaciones"), "motivo", res.get("motivo"))
                break
        else:
            print("timeout_poll")


if __name__ == "__main__":
    main()
