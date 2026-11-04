import json
import ssl
import urllib.error
import urllib.request

ctx = ssl._create_unverified_context()
base = "https://motor-perfilamiento-ia.vercel.app"
body = json.dumps({"usuario": "prueba-scrape", "rol": "admin", "clave": "jefe-prueba-2026"}).encode()
r = urllib.request.urlopen(
    urllib.request.Request(base + "/api/sesion", data=body, method="POST",
                           headers={"Content-Type": "application/json"}),
    timeout=60, context=ctx)
tok = json.loads(r.read().decode())["token"]
q = json.dumps({"pregunta": "cuantos clientes hay por producto"}).encode()
try:
    r = urllib.request.urlopen(
        urllib.request.Request(base + "/api/asistente", data=q, method="POST",
                               headers={"Content-Type": "application/json", "Authorization": "Bearer " + tok}),
        timeout=90, context=ctx)
    res = json.loads(r.read().decode())
except urllib.error.HTTPError as e:
    print("http", e.code, e.read()[:300].decode("utf-8", "replace"))
    raise SystemExit(1)
print("tipo", res.get("tipo"))
print("accion", (res.get("intencion") or {}).get("accion"))
print("keys", sorted(res))
filas = res.get("filas") or res.get("conteo") or res.get("datos")
if isinstance(filas, list):
    print("n_filas", len(filas))
    for f in filas[:8]:
        if isinstance(f, dict):
            print(" fila", {k: f[k] for k in list(f)[:4]})
        else:
            print(" fila", f)
texto = res.get("texto")
if texto:
    print("texto", str(texto)[:400])
