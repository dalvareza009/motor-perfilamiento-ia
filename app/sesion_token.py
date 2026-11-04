"""Sesión firmada: sirve en serverless (Vercel) donde no hay un dict en memoria."""
import base64
import hashlib
import hmac
import json
import os
import time


def _secreto():
    return (os.getenv("SESION_SECRETA") or os.getenv("DEMO_CLAVE") or "dev-local").encode()


def emitir(usuario, rol, horas=12):
    datos = {"usuario": usuario, "rol": rol, "exp": int(time.time() + horas * 3600)}
    cuerpo = base64.urlsafe_b64encode(json.dumps(datos, separators=(",", ":")).encode()).decode().rstrip("=")
    firma = hmac.new(_secreto(), cuerpo.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{cuerpo}.{firma}"


def leer(token):
    if not token or "." not in token:
        return None
    cuerpo, firma = token.split(".", 1)
    esperada = hmac.new(_secreto(), cuerpo.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(firma, esperada):
        return None
    pad = "=" * (-len(cuerpo) % 4)
    try:
        datos = json.loads(base64.urlsafe_b64decode(cuerpo + pad))
    except (json.JSONDecodeError, ValueError):
        return None
    if int(datos.get("exp") or 0) < time.time():
        return None
    usuario, rol = datos.get("usuario"), datos.get("rol")
    if not usuario or not rol:
        return None
    return {"usuario": usuario, "rol": rol}
