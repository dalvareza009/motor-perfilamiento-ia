"""Interfaz web del motor de perfilamiento: API REST (FastAPI) + front estático (carpeta frontend/).

  python -m app.api          ->  http://127.0.0.1:8000

Reutiliza los mismos módulos que la consola (asesor, segmentos, mensajes, governance, ingesta...):
permisos, k-anonimato, validación de borradores y auditoría siguen viviendo en esos módulos.
.env opcional:  WEB_HOST=127.0.0.1   WEB_PUERTO=8000
"""
import argparse
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

os.environ.setdefault("PGCONNECT_TIMEOUT", "8")     # que una BD caída no congele la web

import psycopg2
import requests
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from psycopg2 import sql
from pydantic import BaseModel, ConfigDict, Field

from app import tareas  # noqa: I001  (primero: instala la captura de lo que imprimen los comandos)
from app import (asesor, conocimiento, contenido, deduplicacion, embeddings, facebook_pagina, governance,
                 ingesta_actividad, ingesta_linkedin, ingesta_perfiles, ingesta_web, mensajes, ollama_client,
                 perfil_redes, redes_seguidas, runtime_nube, segmentos, sesion_token, vectorizar)
from app import main as flujo_perfil
from app.database import get_connection

runtime_nube.materializar_cookies()

FRONT = Path(__file__).resolve().parents[1] / "frontend"
ESTADOS_MENSAJE = ["borrador", "requiere_revision", "aprobado", "enviado", "descartado"]

app = FastAPI(title="Motor de perfilamiento IA", docs_url="/api/docs", openapi_url="/api/openapi.json")


# ------------------------------------------------------------------ errores legibles para la interfaz
@app.exception_handler(psycopg2.OperationalError)
async def _sin_bd(_, exc):
    return JSONResponse(status_code=503, content={
        "detail": "No hay conexión con la base de datos. Revisa el .env y que PostgreSQL esté encendido. "
                  f"({str(exc).strip().splitlines()[0][:160] if str(exc).strip() else type(exc).__name__})"})


@app.exception_handler(psycopg2.Error)
async def _error_bd(_, exc):
    detalle = (getattr(exc, "pgerror", None) or str(exc)).strip().splitlines()
    return JSONResponse(status_code=500, content={
        "detail": f"Error de base de datos: {detalle[0][:240] if detalle else type(exc).__name__}"})


@app.exception_handler(requests.exceptions.ConnectionError)
async def _sin_servicio(_, exc):
    return JSONResponse(status_code=503, content={
        "detail": "No se pudo conectar con un servicio externo. ¿Ollama está corriendo en localhost:11434?"})


@app.exception_handler(requests.exceptions.Timeout)
async def _lento(_, exc):
    return JSONResponse(status_code=504, content={"detail": "El modelo tardó demasiado en responder."})


@app.exception_handler(requests.exceptions.HTTPError)
async def _http_modelo(_, exc):
    codigo = getattr(getattr(exc, "response", None), "status_code", None)
    if codigo == 403:
        return JSONResponse(status_code=503, content={
            "detail": "El modelo en la nube pide una tarjeta en Vercel (AI Gateway) para desbloquear créditos. "
                      "Ábrelo en: https://vercel.com/global-a6b2/~/ai"})
    return JSONResponse(status_code=502, content={
        "detail": "El modelo no pudo responder. Revisa LLM_BASE_URL y LLM_API_KEY en Vercel."})


@app.exception_handler(ValueError)
async def _valor(_, exc):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(RuntimeError)
async def _estado_invalido(_, exc):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


# ------------------------------------------------------------------ sesión y permisos
SESIONES = {}


def sesion(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    s = sesion_token.leer(token) or SESIONES.get(token)
    if not s:
        raise HTTPException(401, "Sesión no válida o vencida. Ingresa de nuevo.")
    return s


def exigir(s, accion):
    if not governance.autorizar(s["rol"], accion):
        governance.registrar(s["usuario"], s["rol"], accion, {"origen": "web"}, 0, "denegado")
        raise HTTPException(403, f"Tu rol ({s['rol']}) no tiene permiso para '{accion}'.")


def _permisos(rol):
    return sorted(governance.PERMISOS.get(rol, ()))


class Ingreso(BaseModel):
    usuario: str = Field(min_length=2, max_length=60)
    rol: str
    clave: str = ""


@app.post("/api/sesion")
def ingresar(datos: Ingreso):
    rol = datos.rol.strip().lower()
    if rol not in governance.PERMISOS:
        raise HTTPException(400, f"Rol no válido. Opciones: {', '.join(governance.PERMISOS)}.")
    esperada = os.getenv("DEMO_CLAVE") or ""
    if esperada and datos.clave != esperada:
        raise HTTPException(401, "Clave de acceso incorrecta.")
    token = sesion_token.emitir(datos.usuario.strip(), rol)
    SESIONES[token] = {"usuario": datos.usuario.strip(), "rol": rol}
    return {"token": token, **SESIONES[token], "permisos": _permisos(rol)}


@app.get("/api/sesion")
def sesion_actual(s=Depends(sesion)):
    return {**s, "permisos": _permisos(s["rol"])}


@app.delete("/api/sesion")
def salir(authorization: str = Header(default="")):
    SESIONES.pop(authorization.removeprefix("Bearer ").strip(), None)
    return {"ok": True}


# ------------------------------------------------------------------ utilidades
def _consulta(q, params=()):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(q, params)
            if cur.description is None:
                return []
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()


def _consulta_tolerante(q, params=()):
    """Igual que _consulta, pero vacío si la tabla aún no existe (mensajes, hechos_perfil...)."""
    try:
        return _consulta(q, params)
    except psycopg2.OperationalError:
        raise
    except psycopg2.Error:
        return []


def _filtros_validos(filtros):
    limpios = {}
    for k, v in (filtros or {}).items():
        if k not in segmentos.DIMENSIONES:
            raise HTTPException(400, f"Filtro no permitido: {k}")
        if not isinstance(v, (str, int, bool)) or (isinstance(v, str) and not v.strip()):
            continue
        limpios[k] = v.strip() if isinstance(v, str) else v
    return limpios


def _describir(filtros):
    return ", ".join(f"{k} = {v}" for k, v in filtros.items()) or "todos"


def _diagnostico(filtros):
    filas = [{"filtro": "Sin filtros (todos los clientes)", "n": segmentos.contar_total({})}]
    filas += [{"filtro": f"Solo {k} = {v}", "n": segmentos.contar_total({k: v})} for k, v in filtros.items()]
    return filas


def _correr_comando(fn, args):
    """Corre un comando de consola (cmd_*) y devuelve lo que imprimió. SystemExit -> error 400."""
    with tareas.capturar() as registro:
        try:
            fn(args)
        except SystemExit as e:
            raise HTTPException(400, str(e.code or "La operación se detuvo.")) from None
    return {"ok": True, "log": registro.texto()}


def _mensaje(id_mensaje):
    m = mensajes.obtener(id_mensaje)
    if m:
        m["transiciones"] = sorted(mensajes.TRANSICIONES.get(m["estado"], ()))
    return m


# ------------------------------------------------------------------ estado y catálogos
@app.get("/api/estado")
def estado():
    out = {"bd": {"ok": False}, "ollama": {"ok": False},
           "firecrawl": {"ok": bool(os.getenv("FIRECRAWL_API_KEY")), "sitio": os.getenv("SITIO_DOMINIO")},
           "pide_clave": bool(os.getenv("DEMO_CLAVE"))}
    try:
        _consulta("SELECT 1")
        out["bd"] = {"ok": True}
    except Exception as e:
        out["bd"] = {"ok": False, "detalle": (str(e).strip().splitlines() or [type(e).__name__])[0][:200]}
    modelo = ollama_client._modelo()
    if os.getenv("LLM_BASE_URL"):
        out["ollama"] = {
            "ok": True, "modelos": [modelo], "modelo": modelo, "modelo_ok": True,
            "embed": os.getenv("EMBED_MODEL", embeddings.EMBED_MODEL), "embed_ok": True,
        }
        return out
    base = os.getenv("OLLAMA_URL", ollama_client.OLLAMA_URL).rsplit("/api/", 1)[0]
    try:
        r = requests.get(f"{base}/api/tags", timeout=3)
        r.raise_for_status()
        modelos = [m.get("name", "") for m in r.json().get("models", [])]
        out["ollama"] = {
            "ok": True, "modelos": modelos,
            "modelo": modelo, "modelo_ok": modelo in modelos,
            "embed": embeddings.EMBED_MODEL,
            "embed_ok": any(m.split(":")[0] == embeddings.EMBED_MODEL.split(":")[0] for m in modelos),
        }
    except Exception as e:
        out["ollama"] = {"ok": False, "detalle": type(e).__name__, "modelo": modelo}
    return out


@app.get("/api/catalogo")
def catalogo(s=Depends(sesion)):
    return {
        "dimensiones": sorted(segmentos.DIMENSIONES), "booleanas": sorted(segmentos.COLUMNAS_BOOL),
        "canales": sorted(asesor.CANALES), "estados_mensaje": ESTADOS_MENSAJE,
        "productos_sitio": {k: v[0] for k, v in ingesta_web.CATALOGO.items()},
        "k_min": governance.K_MIN, "limite_lote": asesor.LIMITE_LOTE, "limite_listado": governance.LIMITE_LISTADO,
    }


@app.get("/api/opciones")
def opciones(s=Depends(sesion)):
    """Valores existentes por dimensión, para los selectores (con k-anonimato según el rol)."""
    exigir(s, "contar")
    out = {}
    for dim in sorted(segmentos.DIMENSIONES - segmentos.COLUMNAS_BOOL):
        filas = governance.aplicar_k_anonimato(segmentos.contar_por(dim), s["rol"])
        out[dim] = [v for v, _ in filas if v != "sin_dato"][:300]
    return out


# ------------------------------------------------------------------ panel
@app.get("/api/panel")
def panel(s=Depends(sesion)):
    exigir(s, "contar")
    rol = s["rol"]
    dist = {}
    for dim in ("segmento", "producto_interes", "rango_edad", "ciudad", "genero", "tiene_correo", "tiene_celular"):
        todas = segmentos.contar_por(dim)
        visibles = governance.aplicar_k_anonimato(todas, rol)
        dist[dim] = {"filas": [{"valor": v, "n": n} for v, n in visibles], "ocultos": len(todas) - len(visibles)}
    out = {"total": segmentos.contar_total({}), "distribuciones": dist, "k_min": governance.K_MIN}
    if governance.autorizar(rol, "ver_mensajes"):
        out["mensajes"] = {r["estado"]: r["n"] for r in _consulta_tolerante(
            "SELECT estado, COUNT(*) AS n FROM public.mensajes GROUP BY estado")}
    if governance.autorizar(rol, "admin_conocimiento"):
        filas = _consulta_tolerante("""SELECT COUNT(*) AS n FROM public.conocimiento
                                       WHERE NOT activo AND fuente_url IS NOT NULL""")
        out["pendientes_conocimiento"] = filas[0]["n"] if filas else 0
    if governance.autorizar(rol, "admin_perfiles"):
        filas = _consulta_tolerante("""SELECT COUNT(*) AS n FROM public.hechos_perfil
                                       WHERE NOT activo AND NOT descartado""")
        out["pendientes_hechos"] = filas[0]["n"] if filas else 0
    if governance.autorizar(rol, "admin_clientes"):
        filas = _consulta_tolerante("SELECT COUNT(*) AS n FROM public.par_duplicado WHERE estado = 'pendiente'")
        out["pendientes_duplicados"] = filas[0]["n"] if filas else None
    governance.registrar(s["usuario"], rol, "contar", {"origen": "web", "panel": True}, len(dist))
    return out


# ------------------------------------------------------------------ consultas agregadas (mismas reglas que el asistente)
def _r_contar(intencion, s):
    dim = intencion.get("agrupar_por") or "segmento"
    if dim not in segmentos.DIMENSIONES:
        raise HTTPException(400, f"Dimensión no permitida: {dim}")
    todas = segmentos.contar_por(dim, intencion["filtros"])
    visibles = governance.aplicar_k_anonimato(todas, s["rol"])
    governance.registrar(s["usuario"], s["rol"], "contar", intencion, len(visibles))
    return {"tipo": "conteo", "dimension": dim, "total": sum(n for _, n in todas),
            "filas": [{"valor": v, "n": n} for v, n in visibles],
            "ocultos": len(todas) - len(visibles), "k_min": governance.K_MIN}


def _r_listar(intencion, s):
    filas = segmentos.listar(intencion["filtros"], governance.LIMITE_LISTADO)
    governance.registrar(s["usuario"], s["rol"], "listar", intencion, len(filas))
    out = {"tipo": "listado", "filas": filas, "filtros": intencion["filtros"],
           "agrupar_por": intencion.get("agrupar_por"), "truncado": len(filas) == governance.LIMITE_LISTADO,
           "limite": governance.LIMITE_LISTADO}
    if not filas:
        out["diagnostico"] = _diagnostico(intencion["filtros"])
    return out


def _r_resumen(intencion, s):
    resumen = segmentos.resumen_segmento(intencion["filtros"])
    governance.registrar(s["usuario"], s["rol"], "resumen", intencion, resumen["total"])
    return {"tipo": "resumen", "resumen": resumen, "filtros": intencion["filtros"]}


def _r_plantilla(intencion, s):
    with tareas.capturar():
        texto, resumen, errores = asesor.mensaje_segmento(intencion["filtros"])
    governance.registrar(s["usuario"], s["rol"], "mensaje_segmento", intencion, resumen["total"])
    return {"tipo": "plantilla", "texto": texto, "total": resumen["total"], "errores": errores,
            "filtros": intencion["filtros"]}


class Consulta(BaseModel):
    filtros: dict[str, Any] = {}
    agrupar_por: str | None = None


def _intencion(accion, datos):
    return {"accion": accion, "agrupar_por": datos.agrupar_por, "filtros": _filtros_validos(datos.filtros),
            "origen": "web"}


@app.post("/api/contar")
def contar(datos: Consulta, s=Depends(sesion)):
    exigir(s, "contar")
    return _r_contar(_intencion("contar", datos), s)


@app.post("/api/resumen")
def resumen(datos: Consulta, s=Depends(sesion)):
    exigir(s, "resumen")
    return _r_resumen(_intencion("resumen", datos), s)


@app.post("/api/plantilla")
def plantilla(datos: Consulta, s=Depends(sesion)):
    exigir(s, "mensaje_segmento")
    return _r_plantilla(_intencion("mensaje_segmento", datos), s)


# ------------------------------------------------------------------ clientes
def _buscar_clientes(texto, filtros, limite):
    where, params = segmentos._where(filtros)
    extras, extra_params = [], []
    if texto:      # nombre, clave estable (CL000123), correo o celular
        extras.append(sql.SQL("(nombre ILIKE %s OR clave_cliente = %s OR correo = LOWER(%s) OR celular = %s)"))
        extra_params += [f"%{texto}%", texto, texto, perfil_redes.normalizar_celular(texto)]
    if segmentos.CONSENT_COLUMN:
        extras.append(sql.SQL("{} = TRUE").format(sql.Identifier(segmentos.CONSENT_COLUMN)))
    if extras:
        union = sql.SQL(" AND ").join(extras)
        where = (where + sql.SQL(" AND ") + union) if params else (sql.SQL("WHERE ") + union)
    cols = segmentos.COLUMNAS_LISTADO + ["tiene_correo", "tiene_celular"]
    q = sql.SQL("SELECT {c} FROM {v} {w} ORDER BY nombre LIMIT %s").format(
        c=sql.SQL(", ").join(map(sql.Identifier, cols)), v=segmentos.VISTA, w=where)
    return _consulta(q, params + extra_params + [int(limite)])


# Las claves de cliente pueden ser un correo o un celular: viajan en el cuerpo (POST), nunca en la URL,
# para que no queden en logs de acceso ni en el historial del navegador.
class BusquedaClientes(BaseModel):
    q: str = ""
    filtros: dict[str, Any] = {}


class Clave(BaseModel):
    clave: str = Field(min_length=1)


@app.post("/api/clientes/buscar")
def clientes(datos: BusquedaClientes, s=Depends(sesion)):
    exigir(s, "listar")
    f = _filtros_validos(datos.filtros)
    filas = _buscar_clientes(datos.q.strip(), f, governance.LIMITE_LISTADO)
    governance.registrar(s["usuario"], s["rol"], "listar",
                         {"origen": "web", "texto": datos.q.strip(), "filtros": f}, len(filas))
    return {"filas": filas, "truncado": len(filas) == governance.LIMITE_LISTADO, "limite": governance.LIMITE_LISTADO}


@app.post("/api/clientes/ficha")
def cliente(datos: Clave, s=Depends(sesion)):
    exigir(s, "listar")
    clave = datos.clave.strip()
    ficha = mensajes.obtener_cliente(clave)
    if not ficha:
        raise HTTPException(404, "No existe ese cliente.")
    # SELECT *: con la deduplicación instalada trae además n_registros, correos, celulares y productos.
    extra = _consulta("SELECT * FROM public.clientes_segmentados WHERE clave_cliente = %s", (clave,))
    extra = [{k: v for k, v in extra[0].items()
              if k in ("segmento", "rango_edad", "n_registros", "correos", "celulares", "productos_interes")}] \
        if extra else []
    hechos = _consulta_tolerante("""SELECT id_hecho, red, categoria, titulo, contenido, activo, descartado,
                                           fuente_url
                                    FROM public.hechos_perfil WHERE clave_cliente = %s
                                    ORDER BY activo DESC, id_hecho""", (clave,))
    msgs = _consulta_tolerante("""SELECT id_mensaje, canal, producto, estado, fecha_creacion
                                  FROM public.mensajes WHERE clave_cliente = %s
                                  ORDER BY id_mensaje DESC""", (clave,))
    try:
        perfil = flujo_perfil.get_profile(clave)
    except psycopg2.OperationalError:
        raise
    except psycopg2.Error:
        perfil = None
    governance.registrar(s["usuario"], s["rol"], "ver_cliente", {"origen": "web", "clave": clave}, 1)
    return {"ficha": {**ficha, **(extra[0] if extra else {})}, "hechos": hechos, "mensajes": msgs, "perfil": perfil,
            "registros": deduplicacion.registros_de(clave)}


def _borrador_para(clave, canal, s, intencion=None):
    canal = (canal or "").strip().lower()
    if canal not in asesor.CANALES:
        raise HTTPException(400, "Canal no válido: usa correo o whatsapp.")
    cliente_ = mensajes.obtener_cliente(clave)
    if cliente_ is None:
        raise HTTPException(404, "No se pudo cargar la ficha de ese cliente.")
    with tareas.capturar():
        r = mensajes.generar_para_cliente(cliente_, canal, s["usuario"])
    governance.registrar(s["usuario"], s["rol"], "mensaje_cliente",
                         {**(intencion or {"accion": "mensaje_cliente", "origen": "web"}),
                          "clave": clave, "canal": canal, "resultado": r["estado_proceso"]},
                         1 if r["estado_proceso"] != "omitido" else 0)
    out = {"tipo": "borrador", "resultado": r,
           "cliente": {"clave_cliente": clave, "nombre": cliente_["nombre"]}}
    if r.get("id"):
        out["mensaje"] = _mensaje(r["id"])
    return out


class PedidoBorrador(Clave):
    canal: str


@app.post("/api/clientes/borrador")
def borrador(datos: PedidoBorrador, s=Depends(sesion)):
    exigir(s, "mensaje_cliente")
    return _borrador_para(datos.clave.strip(), datos.canal, s)


@app.post("/api/clientes/perfil")
def perfil_ia(datos: Clave, s=Depends(sesion)):
    """Perfil consolidado con el LLM (flujo de app/main.py), guardado en public.perfiles."""
    exigir(s, "mensaje_cliente")
    clave = datos.clave.strip()
    cliente_ = flujo_perfil.get_consolidated_client(clave)
    if not cliente_:
        raise HTTPException(404, "Ese cliente no está en clientes_consolidados.")
    with tareas.capturar():
        datos = ollama_client.generate_json(flujo_perfil.build_profile_prompt(cliente_))
    campos = ("segmento", "caracteristicas_relevantes", "perfil_consolidado")
    if not isinstance(datos, dict) or not all(datos.get(c) for c in campos):
        raise HTTPException(502, "El modelo no devolvió un perfil válido. Intenta de nuevo.")
    perfil = {c: ", ".join(map(str, datos[c])) if isinstance(datos[c], list) else str(datos[c]) for c in campos}
    id_perfil = flujo_perfil.save_profile(cliente_, perfil)
    governance.registrar(s["usuario"], s["rol"], "perfil_cliente", {"origen": "web", "clave": clave}, 1)
    return {"perfil": flujo_perfil.get_saved_profile(id_perfil)}


# ------------------------------------------------------------------ borradores
@app.get("/api/mensajes")
def listar_mensajes(estado: str = "", limite: int = 200, s=Depends(sesion)):
    exigir(s, "ver_mensajes")
    filas = mensajes.listar(estado or None, min(max(limite, 1), 500))
    conteo = {r["estado"]: r["n"] for r in _consulta_tolerante(
        "SELECT estado, COUNT(*) AS n FROM public.mensajes GROUP BY estado")}
    governance.registrar(s["usuario"], s["rol"], "ver_mensajes", {"origen": "web", "estado": estado or None},
                         len(filas))
    cols = ("id_mensaje", "nombre", "canal", "estado", "producto", "fecha_creacion")
    return {"filas": [dict(zip(cols, f)) for f in filas], "conteo": conteo}


@app.get("/api/mensajes/{id_mensaje}")
def ver_mensaje(id_mensaje: int, s=Depends(sesion)):
    exigir(s, "ver_mensajes")
    m = _mensaje(id_mensaje)
    governance.registrar(s["usuario"], s["rol"], "ver_mensajes", {"origen": "web", "id": id_mensaje}, 1 if m else 0)
    if not m:
        raise HTTPException(404, "No existe ese mensaje.")
    return m


class CambioEstado(BaseModel):
    estado: str


@app.post("/api/mensajes/{id_mensaje}/estado")
def cambiar_estado(id_mensaje: int, datos: CambioEstado, s=Depends(sesion)):
    exigir(s, "cambiar_estado")
    ok, texto = mensajes.cambiar_estado(id_mensaje, datos.estado, s["usuario"])
    governance.registrar(s["usuario"], s["rol"], "cambiar_estado",
                         {"origen": "web", "id": id_mensaje, "nuevo": datos.estado}, 1 if ok else 0,
                         "ok" if ok else "denegado")
    if not ok:
        raise HTTPException(409, texto)
    return {"ok": True, "texto": texto, "mensaje": _mensaje(id_mensaje)}


def _correr_lote(tarea, filtros, canal, s):
    lista = segmentos.listar(filtros, asesor.LIMITE_LOTE)
    tarea.avance(0, len(lista))
    if not lista:
        print("Sin clientes en ese grupo.")
        return {"total": 0, "resultados": [], "diagnostico": _diagnostico(filtros)}
    resultados = []
    for i, c in enumerate(lista, 1):
        print(f"[{i}/{len(lista)}] {c['nombre']}...")
        try:
            ficha = mensajes.obtener_cliente(c["clave_cliente"])
            r = (mensajes.generar_para_cliente(ficha, canal, s["usuario"]) if ficha
                 else {"estado_proceso": "omitido", "motivo": "no se pudo cargar la ficha"})
        except requests.exceptions.RequestException as e:
            r = {"estado_proceso": "omitido", "motivo": f"el modelo no respondió ({type(e).__name__})"}
        detalle = r.get("motivo") or r.get("estado") or ""
        print(f"      {r['estado_proceso']}{' #' + str(r['id']) if r.get('id') else ''} {detalle}")
        resultados.append({"clave_cliente": c["clave_cliente"], "nombre": c["nombre"], **r})
        tarea.avance(i)
    generados = sum(1 for r in resultados if r["estado_proceso"] == "generado")
    governance.registrar(s["usuario"], s["rol"], "mensajes_lote",
                         {"accion": "mensajes_lote", "origen": "web", "filtros": filtros, "canal": canal}, generados)
    return {"total": len(lista), "resultados": resultados}


class PedidoLote(BaseModel):
    filtros: dict[str, Any] = {}
    canal: str


@app.post("/api/mensajes/lote")
def lote(datos: PedidoLote, s=Depends(sesion)):
    exigir(s, "mensajes_lote")
    filtros, canal = _filtros_validos(datos.filtros), datos.canal.strip().lower()
    if not filtros:
        raise HTTPException(400, "Para generar en lote indica un grupo (por ejemplo, el producto o la ciudad).")
    if canal not in asesor.CANALES:
        raise HTTPException(400, "Canal no válido: usa correo o whatsapp.")
    t = tareas.lanzar("lote", f"Borradores por {canal} · {_describir(filtros)}", s["usuario"],
                      _correr_lote, filtros, canal, dict(s))
    return {"tipo": "tarea", "tarea": t.vista()}


# ------------------------------------------------------------------ tareas en segundo plano
def _resumen_tarea(t):
    v = t.vista()
    v.pop("lineas")
    return v


@app.get("/api/tareas")
def lista_tareas(s=Depends(sesion)):
    usuario = None if s["rol"] == "admin" else s["usuario"]
    return [_resumen_tarea(t) for t in tareas.recientes(usuario)]


@app.get("/api/tareas/{id_tarea}")
def ver_tarea(id_tarea: str, desde: int = 0, s=Depends(sesion)):
    t = tareas.obtener(id_tarea)
    if not t or (t.usuario != s["usuario"] and s["rol"] != "admin"):
        raise HTTPException(404, "No existe esa tarea (las tareas se pierden al reiniciar el servidor).")
    return t.vista(max(desde, 0))


@app.post("/api/tareas/{id_tarea}/cancelar")
def cancelar_tarea(id_tarea: str, s=Depends(sesion)):
    t = tareas.obtener(id_tarea)
    if not t or (t.usuario != s["usuario"] and s["rol"] != "admin"):
        raise HTTPException(404, "No existe esa tarea.")
    if t.estado != "en_curso":
        return {"ok": True, "tarea": t.vista()}
    tareas.marcar_cancelada(t)
    return {"ok": True, "tarea": t.vista()}


# ------------------------------------------------------------------ asistente en lenguaje natural
def _r_mensaje_cliente(intencion, s):
    if not intencion["nombre"]:
        return {"tipo": "aviso", "texto": "¿Para qué cliente? Indica su nombre o su clave."}
    coincidencias = mensajes.buscar_cliente(intencion["nombre"])
    if not coincidencias:
        return {"tipo": "aviso", "texto": f"No encontré clientes que coincidan con '{intencion['nombre']}'."}
    opciones_ = [{"clave_cliente": c[0], "nombre": c[1], "ciudad": c[2]} for c in coincidencias]
    if len(opciones_) > 1:
        return {"tipo": "elegir_cliente", "opciones": opciones_, "canal": intencion["canal"],
                "texto": "Hay varios clientes que coinciden. ¿Cuál?"}
    if not intencion["canal"]:
        return {"tipo": "elegir_canal", "cliente": opciones_[0], "texto": "¿Por qué canal: correo o WhatsApp?"}
    return _borrador_para(opciones_[0]["clave_cliente"], intencion["canal"], s, intencion)


def _r_lote(intencion, s):
    """En la web el lote se confirma antes de lanzar: una mala interpretación no genera 50 borradores."""
    if not intencion["filtros"]:
        return {"tipo": "aviso", "texto": "Para generar en lote indica un grupo (por ejemplo, el producto o la ciudad)."}
    total = segmentos.contar_total(intencion["filtros"])
    return {"tipo": "confirmar_lote", "filtros": intencion["filtros"], "canal": intencion["canal"],
            "total": total, "limite": asesor.LIMITE_LOTE}


MANEJADORES = {"contar": _r_contar, "listar": _r_listar, "resumen": _r_resumen,
               "mensaje_segmento": _r_plantilla, "mensaje_cliente": _r_mensaje_cliente, "mensajes_lote": _r_lote}


def _comando(linea, s):
    partes = linea.split()
    if partes[0] == "/ver" and len(partes) > 1 and partes[1].isdigit():
        if not governance.autorizar(s["rol"], "ver_mensajes"):
            return {"tipo": "aviso", "texto": f"Tu rol ({s['rol']}) no tiene permiso para ver borradores."}
        m = _mensaje(int(partes[1]))
        governance.registrar(s["usuario"], s["rol"], "ver_mensajes", {"origen": "web", "id": int(partes[1])},
                             1 if m else 0)
        return {"tipo": "mensaje", "mensaje": m} if m else {"tipo": "aviso", "texto": "No existe ese mensaje."}
    with tareas.capturar():
        texto = asesor.comando(linea, s["usuario"], s["rol"])
    return {"tipo": "texto", "texto": texto}


class Pregunta(BaseModel):
    pregunta: str = Field(min_length=1, max_length=1000)


@app.post("/api/asistente")
def asistente(datos: Pregunta, s=Depends(sesion)):
    pregunta = datos.pregunta.strip()
    if pregunta.startswith("/"):
        return _comando(pregunta, s)
    with tareas.capturar():
        intencion = asesor.sanear(asesor.interpretar(pregunta))
    if intencion is None:
        return {"tipo": "aviso", "texto": "No pude interpretar la solicitud. ¿Puedes reformularla?"}
    if intencion["no_soportado"]:
        return {"tipo": "aviso", "intencion": intencion,
                "texto": "No tengo estos datos disponibles: " + ", ".join(intencion["no_soportado"]) +
                         ". No ejecuté la consulta para no devolverte una lista que ignore ese criterio. "
                         "Reformula sin ellos."}
    accion = intencion["accion"]
    if not governance.autorizar(s["rol"], accion):
        governance.registrar(s["usuario"], s["rol"], accion, intencion, 0, "denegado")
        return {"tipo": "aviso", "intencion": intencion, "texto": f"Tu rol ({s['rol']}) no tiene permiso para '{accion}'."}
    return {"intencion": intencion, **MANEJADORES[accion](intencion, s)}


# ------------------------------------------------------------------ conocimiento de producto (admin)
@app.get("/api/conocimiento/resumen")
def conocimiento_resumen(s=Depends(sesion)):
    exigir(s, "admin_conocimiento")
    return _consulta("""SELECT producto, categoria,
                               COUNT(*) FILTER (WHERE NOT activo AND fuente_url IS NOT NULL) AS pendientes,
                               COUNT(*) FILTER (WHERE activo) AS activos,
                               COUNT(*) FILTER (WHERE fuente_url IS NULL) AS manuales
                        FROM public.conocimiento GROUP BY 1, 2 ORDER BY 1, 2""")


@app.get("/api/conocimiento")
def conocimiento_lista(estado: str = "pendiente", producto: str = "", categoria: str = "", q: str = "",
                       limite: int = 150, s=Depends(sesion)):
    exigir(s, "admin_conocimiento")
    where = {"pendiente": ["NOT activo", "fuente_url IS NOT NULL"], "activo": ["activo"],
             "inactivo": ["NOT activo"]}.get(estado, ["TRUE"])
    params = []
    if producto:
        where.append("LOWER(producto) = LOWER(%s)")
        params.append(producto)
    if categoria:
        where.append("LOWER(categoria) = LOWER(%s)")
        params.append(categoria)
    if q.strip():
        where.append("(titulo ILIKE %s OR contenido ILIKE %s)")
        params += [f"%{q.strip()}%"] * 2
    condicion = " AND ".join(where)
    filas = _consulta(f"""SELECT id_conocimiento, producto, categoria, titulo, contenido, activo, fuente_url,
                                 fecha_actualizacion
                          FROM public.conocimiento WHERE {condicion}
                          ORDER BY id_conocimiento LIMIT %s""", params + [min(max(limite, 1), 500)])
    total = _consulta(f"SELECT COUNT(*) AS n FROM public.conocimiento WHERE {condicion}", params)[0]["n"]
    return {"filas": filas, "total": total}


class Seleccion(BaseModel):
    ids: list[int] = []
    todos: bool = False
    producto: str | None = None
    categoria: str | None = None
    grupo: str = ""


@app.post("/api/conocimiento/aprobar")
def conocimiento_aprobar(datos: Seleccion, s=Depends(sesion)):
    exigir(s, "admin_conocimiento")
    return _correr_comando(ingesta_web.cmd_aprobar, argparse.Namespace(
        ids=datos.ids, todos=datos.todos, producto=datos.producto or None, categoria=datos.categoria or None,
        usuario=s["usuario"]))


@app.post("/api/conocimiento/desactivar")
def conocimiento_desactivar(datos: Seleccion, s=Depends(sesion)):
    exigir(s, "admin_conocimiento")
    if not datos.ids:
        raise HTTPException(400, "Indica qué fragmentos desactivar.")
    return _correr_comando(ingesta_web.cmd_desactivar, argparse.Namespace(ids=datos.ids, usuario=s["usuario"]))


@app.post("/api/conocimiento/vectorizar")
def conocimiento_vectorizar(s=Depends(sesion)):
    exigir(s, "admin_conocimiento")
    with tareas.capturar():
        r = vectorizar.sincronizar()
    governance.registrar(s["usuario"], s["rol"], "vectorizar", {"origen": "web"}, r["vectorizados"])
    return r


class PruebaRag(BaseModel):
    producto: str = ""
    consulta: str = Field(min_length=2, max_length=500)
    k: int = Field(default=5, ge=1, le=20)


@app.post("/api/conocimiento/buscar")
def conocimiento_buscar(datos: PruebaRag, s=Depends(sesion)):
    """Prueba de recuperación: qué fragmentos recibiría el modelo para esa consulta."""
    exigir(s, "admin_conocimiento")
    producto = datos.producto.strip() or None
    fragmentos, aviso = [], None
    with tareas.capturar() as registro:
        try:
            fragmentos = conocimiento.buscar_fragmentos(producto, datos.consulta, datos.k)
        except Exception as e:
            aviso = f"Búsqueda vectorial no disponible ({type(e).__name__}). Se usaría el conocimiento completo."
        texto, titulos, modo = conocimiento.recuperar(producto, datos.consulta, datos.k)
    return {"modo": modo, "titulos": titulos, "texto": texto, "fragmentos": fragmentos, "aviso": aviso,
            "log": registro.texto()}


class PedidoIngesta(BaseModel):
    modo: str = "sitio"                 # sitio | scrape
    solo: list[str] = []
    sin_portafolio: bool = False
    producto: str = "auto"
    urls: list[str] = []
    pdf: bool = False
    pdf_solo: str = ""
    max_pdfs: int = Field(default=5, ge=1, le=50)
    max_fragmentos: int = Field(default=120, ge=10, le=500)
    con_tarifas: bool = False


@app.post("/api/conocimiento/ingesta")
def conocimiento_ingesta(datos: PedidoIngesta, s=Depends(sesion)):
    exigir(s, "admin_conocimiento")
    pdf = {"pdf": datos.pdf, "pdf_solo": datos.pdf_solo, "max_pdfs": datos.max_pdfs,
           "max_fragmentos": datos.max_fragmentos, "con_tarifas": datos.con_tarifas, "usuario": s["usuario"]}
    if datos.modo == "sitio":
        malos = [x for x in datos.solo if x not in ingesta_web.CATALOGO]
        if malos:
            raise HTTPException(400, f"Productos desconocidos: {', '.join(malos)}")
        args = argparse.Namespace(solo=datos.solo or None, sin_portafolio=datos.sin_portafolio, **pdf)
        fn, desc = ingesta_web.cmd_sitio, "Sitio: " + (", ".join(datos.solo) or "todo el catálogo")
    elif datos.modo == "scrape":
        urls = [u.strip() for u in datos.urls if u.strip()]
        if not urls:
            raise HTTPException(400, "Indica al menos una URL.")
        args = argparse.Namespace(producto=datos.producto.strip() or "auto", urls=urls, **pdf)
        fn, desc = ingesta_web.cmd_scrape, f"Páginas sueltas ({len(urls)}) → {args.producto}"
    else:
        raise HTTPException(400, "Modo no válido: sitio o scrape.")
    t = tareas.lanzar("ingesta_web", desc, s["usuario"], lambda _t, a: fn(a), args)
    governance.registrar(s["usuario"], s["rol"], "ingesta_web",
                         {"origen": "web", **datos.model_dump(exclude={"urls"}), "urls": len(datos.urls)}, 0)
    return {"tarea": t.vista()}


# ------------------------------------------------------------------ perfiles públicos autorizados (admin)
class PersonaAutorizada(BaseModel):
    model_config = ConfigDict(extra="allow")
    nombre: str = ""
    clave_cliente: str = ""
    autorizado: bool = False
    autorizacion: str = ""
    urls: list[str] = []


class Autorizados(BaseModel):
    personas: list[PersonaAutorizada]


@app.get("/api/perfiles/autorizados")
def autorizados(s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    archivo = ingesta_perfiles.ARCHIVO
    if not archivo.is_file():
        return {"personas": [], "existe": False,
                "avisos": ["Aún no existe data/perfiles_autorizados.json: se creará al guardar."]}
    try:
        data = json.loads(archivo.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"data/perfiles_autorizados.json no es un JSON válido: {e}") from None
    data = data if isinstance(data, list) else []
    _, avisos = perfil_redes.cargar_autorizados(data)
    return {"personas": data, "avisos": avisos, "existe": True}


@app.put("/api/perfiles/autorizados")
def guardar_autorizados(datos: Autorizados, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    data = []
    for p in datos.personas:
        d = p.model_dump()
        d.update(nombre=d["nombre"].strip(), clave_cliente=d["clave_cliente"].strip(),
                 autorizacion=d["autorizacion"].strip(), urls=[u.strip() for u in d["urls"] if u.strip()])
        data.append(d)
    archivo = ingesta_perfiles.ARCHIVO
    archivo.parent.mkdir(parents=True, exist_ok=True)
    temporal = archivo.with_suffix(".json.tmp")
    temporal.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporal, archivo)
    _, avisos = perfil_redes.cargar_autorizados(data)
    governance.registrar(s["usuario"], s["rol"], "editar_autorizados",
                         {"origen": "web", "personas": [d["nombre"] for d in data]}, len(data))
    return {"ok": True, "avisos": avisos}


TOPE_LOTE = 50


class PedidoLectura(BaseModel):
    nombres: list[str] = []
    urls: list[str] = []
    max_posts: int = Field(default=10, ge=1, le=10)
    todos: bool = False


def _objetivos_lote(nombres, urls, todos=False):
    """URLs pegadas se leen tal cual. Sin URLs no se tocan las personas autorizadas viejas."""
    objetivos, avisos = ingesta_perfiles.objetivos_de_pedido(nombres, urls, todos=todos)
    for aviso in avisos:
        print(f"· {aviso}")
    return objetivos, avisos


def _correr_ingesta_perfiles(tarea, nombres, urls, max_posts, usuario, todos=False):
    """Un Chrome por red: lee hasta 50 perfiles seguidos, sin reabrir el navegador."""
    tope = redes_seguidas.tope_publicaciones(max_posts)
    urls_limpias = [str(u).strip() for u in (urls or []) if u and str(u).strip()]
    if urls_limpias:
        print(f"Solo las {len(urls_limpias)} URL(s) pegadas. No se leen Personas autorizadas.")
        for u in urls_limpias:
            print(f"  · {u}")
        objetivos, avisos = ingesta_perfiles.objetivos_desde_urls(urls_limpias, data=[])
        for aviso in avisos:
            print(f"· {aviso}")
    else:
        objetivos, avisos = _objetivos_lote(nombres, [], todos=todos)
    if not objetivos:
        raise SystemExit(avisos[0] if avisos else
                         "Pega URLs de LinkedIn, Facebook, Instagram o X, una por línea.")
    if len(objetivos) > TOPE_LOTE:
        print(f"Este lote toma los primeros {TOPE_LOTE} perfiles (había {len(objetivos)}).")
        objetivos = objetivos[:TOPE_LOTE]
    por_red = {}
    for persona, perfil in objetivos:
        por_red.setdefault(perfil["red"], []).append((persona, perfil))
    resultados, hechos, total = [], 0, len(objetivos)
    tarea.avance(0, total)
    print(f"{total} perfil(es); {tope} publicación(es) por perfil.")
    for red, items in por_red.items():
        if getattr(tarea, "cancelada", False):
            print("Tarea detenida.")
            break
        bot = _abrir_bot(red, tarea)
        tarea.bot = bot
        if not bot:
            for persona, perfil in items:
                resultados.append({
                    "ok": False, "perfil": perfil["url"], "red": red,
                    "nombre": persona.get("nombre") or perfil["url"],
                    "motivo": f"No se confirmó el inicio de sesión en {red}.",
                })
                hechos += 1
                tarea.avance(hechos, total)
            continue
        try:
            for persona, perfil in items:
                if getattr(tarea, "cancelada", False):
                    print("Tarea detenida.")
                    break
                url = perfil["url"]
                print(f"\n--- {persona.get('nombre') or url}: {red} {url} ---")
                res = _procesar_con_bot(red, bot, url, tope, usuario, True)
                info = dict(res.get("perfil_info") or {})
                nombre = info.get("nombre") or persona.get("nombre") or ""
                if res.get("ok") and nombre and not info.get("nombre"):
                    info["nombre"] = nombre
                    res = {**res, "perfil_info": info}
                resultados.append({**res, "red": red, "nombre": nombre})
                hechos += 1
                tarea.avance(hechos, total)
        finally:
            tarea.bot = None
            bot.cerrar_navegador(preguntar=False)
    return {"ok": any(r.get("ok") for r in resultados), "resultados": resultados}


def _correr_lote(tarea, urls, max_posts, usuario):
    """Nunca lee Personas autorizadas: solo las URLs del pedido."""
    urls_limpias = [str(u).strip() for u in (urls or []) if u and str(u).strip()]
    if not urls_limpias:
        raise SystemExit("El lote no tiene URLs. No se leen personas autorizadas.")
    return _correr_ingesta_perfiles(tarea, [], urls_limpias, max_posts, usuario, todos=False)


@app.post("/api/perfiles/ingesta")
def perfiles_ingesta(datos: PedidoLectura, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    urls = [u.strip() for u in datos.urls if u and str(u).strip()]
    nombres = [n.strip() for n in datos.nombres if n and str(n).strip()]
    if not urls and not nombres and not datos.todos:
        raise HTTPException(
            status_code=400,
            detail="Pega al menos una URL. Extraer lote no lee las personas autorizadas anteriores.",
        )
    if urls:
        desc = f"Lote: {len(urls)} URL(s)"
        tipo = "ingesta_lote"
        tareas.cancelar_tipo("ingesta_perfiles")
    elif nombres:
        desc = "Perfiles: " + ", ".join(nombres)
        tipo = "ingesta_perfiles"
    else:
        desc = "Perfiles: todas las personas autorizadas"
        tipo = "ingesta_perfiles"
    t = tareas.lanzar(tipo, desc, s["usuario"], _correr_ingesta_perfiles,
                      nombres, urls, datos.max_posts, s["usuario"], datos.todos)
    governance.registrar(s["usuario"], s["rol"], tipo,
                         {"origen": "web", "nombres": nombres, "urls": len(urls),
                          "max_posts": datos.max_posts, "todos": datos.todos}, 0)
    return {"tarea": t.vista()}


class PedidoLote(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=50)
    max_posts: int = Field(default=10, ge=1, le=10)


@app.get("/api/perfiles/lote")
def perfiles_lote_listo(s=Depends(sesion)):
    """Si esto responde, el servidor ya no cae a Personas autorizadas al extraer un lote."""
    exigir(s, "admin_perfiles")
    return {"solo_urls": True, "tope": TOPE_LOTE}


@app.post("/api/perfiles/lote")
def perfiles_lote(datos: PedidoLote, s=Depends(sesion)):
    """Extrae únicamente las URLs pegadas. No abre Personas autorizadas."""
    exigir(s, "admin_perfiles")
    urls = [u.strip() for u in datos.urls if u and str(u).strip()]
    if not urls:
        raise HTTPException(400, "Pega al menos una URL de perfil. El lote no lee Personas autorizadas.")
    for t in tareas.recientes(s["usuario"]):
        if t.estado == "en_curso" and (
            t.tipo == "ingesta_perfiles" or "autorizad" in (t.descripcion or "").lower()
        ):
            tareas.marcar_cancelada(t)
    desc = f"Lote: {len(urls)} URL(s)"
    t = tareas.lanzar("ingesta_lote", desc, s["usuario"], _correr_lote,
                      urls, datos.max_posts, s["usuario"])
    governance.registrar(s["usuario"], s["rol"], "ingesta_lote",
                         {"origen": "web", "urls": urls, "max_posts": datos.max_posts}, 0)
    return {"solo_urls": True, "urls": urls, "tarea": t.vista()}


@app.get("/api/mensajes-prueba")
def mensajes_prueba_lista(s=Depends(sesion)):
    """Tres borradores de prueba por prospecto, listos para revisar."""
    exigir(s, "admin_perfiles")
    from app import mensajes_prueba
    return mensajes_prueba.listar()


@app.get("/api/perfiles/personas")
def perfiles_personas(s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    ingesta_perfiles.asegurar_tabla()
    cats = contenido.excluidas_de_ficha()
    cats_red = list(redes_seguidas.CATEGORIAS_RED)
    return _consulta("""SELECT nombre, MAX(clave_cliente) AS clave_cliente,
                               COUNT(*) FILTER (WHERE NOT activo AND NOT descartado
                                    AND categoria <> ALL(%s)) AS pendientes,
                               COUNT(*) FILTER (WHERE NOT activo AND NOT descartado
                                    AND categoria = ANY(%s)) AS pendientes_red,
                               COUNT(*) FILTER (WHERE activo) AS aprobados,
                               COUNT(*) FILTER (WHERE descartado AND NOT activo) AS descartados,
                               STRING_AGG(DISTINCT red, ', ') AS redes,
                               MAX(fecha_actualizacion) AS actualizado
                        FROM public.hechos_perfil GROUP BY nombre ORDER BY nombre""",
                     (cats, cats_red))


class FiltroHechos(BaseModel):
    nombre: str = ""
    estado: str = "pendiente"
    grupo: str = ""
    limite: int = Field(default=500, ge=1, le=5000)


@app.post("/api/perfiles/hechos/lista")
def perfiles_hechos(datos: FiltroHechos, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    ingesta_perfiles.asegurar_tabla()
    nombre = datos.nombre.strip()
    where = {"pendiente": "NOT activo AND NOT descartado", "aprobado": "activo",
             "descartado": "descartado AND NOT activo"}.get(datos.estado, "TRUE")
    cats_red = list(redes_seguidas.CATEGORIAS_RED)
    cats_fuera = contenido.excluidas_de_ficha()
    if datos.grupo == "red":
        where += " AND categoria = ANY(%s)"
        params = (cats_red, nombre, nombre, datos.limite)
    elif datos.grupo == "contenido":
        where += " AND categoria = ANY(%s)"
        params = (list(contenido.CATEGORIAS_CONTENIDO), nombre, nombre, datos.limite)
    else:
        where += " AND NOT (categoria = ANY(%s))"
        params = (cats_fuera, nombre, nombre, datos.limite)
    return _consulta(f"""SELECT id_hecho, nombre, clave_cliente, red, fuente_url, categoria, titulo, contenido,
                                activo, descartado, fecha_actualizacion
                         FROM public.hechos_perfil
                         WHERE {where} AND (%s = '' OR LOWER(nombre) = LOWER(%s))
                         ORDER BY CASE categoria
                            WHEN 'Gusto' THEN 0
                            WHEN 'Sigue a' THEN 1
                            WHEN 'Repost' THEN 2
                            WHEN 'Seguidor' THEN 3
                            ELSE 4 END, titulo, id_hecho DESC
                         LIMIT %s""",
                     params)


@app.post("/api/perfiles/hechos/aprobar")
def perfiles_aprobar(datos: Seleccion, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return _correr_comando(ingesta_perfiles.cmd_aprobar,
                           argparse.Namespace(ids=datos.ids, todos=datos.todos, grupo=datos.grupo,
                                              usuario=s["usuario"]))


@app.post("/api/perfiles/hechos/descartar")
def perfiles_descartar(datos: Seleccion, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return _correr_comando(ingesta_perfiles.cmd_descartar, argparse.Namespace(ids=datos.ids, usuario=s["usuario"]))


class FiltroContenido(BaseModel):
    nombre: str = ""
    red: str = ""
    limite: int = Field(default=500, ge=1, le=2000)


@app.post("/api/perfiles/contenido")
def perfiles_contenido(datos: FiltroContenido, s=Depends(sesion)):
    """Publicaciones de todas las redes de las personas a las que se les hizo scraping."""
    exigir(s, "admin_perfiles")
    return contenido.listar(nombre=datos.nombre, red=datos.red, limite=datos.limite)


class NombrePersona(BaseModel):
    nombre: str = Field(min_length=1)


@app.post("/api/perfiles/persona")
def perfiles_persona(datos: NombrePersona, s=Depends(sesion)):
    """Todo lo necesario para decidir: hechos, datos derivados, clientes que coinciden y la oferta."""
    exigir(s, "admin_perfiles")
    ingesta_perfiles.asegurar_tabla()
    nombre = datos.nombre
    hechos = _consulta("""SELECT id_hecho, red, fuente_url, categoria, titulo, contenido, clave_cliente,
                                 activo, descartado
                          FROM public.hechos_perfil WHERE LOWER(nombre) = LOWER(%s)
                          ORDER BY id_hecho""", (nombre.strip(),))
    if not hechos:
        raise HTTPException(404, f"No hay hechos de perfil para '{nombre}'.")
    aprobados = [h for h in hechos if h["activo"]]
    clave = next((h["clave_cliente"] for h in hechos if h["clave_cliente"]), None)
    candidatos = ingesta_perfiles._clientes_por_nombre(nombre)
    if clave and not any(c["clave_cliente"] == clave for c in candidatos):
        candidatos = [c for c in ingesta_perfiles._clientes_por_nombre(clave) if c["clave_cliente"] == clave] + candidatos
    vinculado = next((c for c in candidatos if c["clave_cliente"] == clave), None) if clave else None
    return {"nombre": nombre.strip(), "hechos": hechos, "clave_cliente": clave,
            "datos": perfil_redes.datos_para_cliente(aprobados) if aprobados else None,
            "clientes": candidatos, "vinculado": vinculado}


class Vinculo(BaseModel):
    nombre: str
    clave: str = ""
    producto: str = ""


@app.post("/api/perfiles/vincular")
def perfiles_vincular(datos: Vinculo, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    if not datos.clave.strip():
        raise HTTPException(400, "Indica la clave del cliente.")
    return _correr_comando(ingesta_perfiles.cmd_vincular,
                           argparse.Namespace(nombre=datos.nombre, clave=datos.clave, usuario=s["usuario"]))


@app.post("/api/perfiles/completar")
def perfiles_completar(datos: Vinculo, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return _correr_comando(ingesta_perfiles.cmd_completar,
                           argparse.Namespace(nombre=datos.nombre, clave=datos.clave, usuario=s["usuario"]))


@app.post("/api/perfiles/incorporar")
def perfiles_incorporar(datos: Vinculo, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return _correr_comando(ingesta_perfiles.cmd_incorporar,
                           argparse.Namespace(nombre=datos.nombre, producto=datos.producto, usuario=s["usuario"]))


# ------------------------------------------------------------------ duplicados de clientes (admin)
@app.get("/api/duplicados")
def duplicados(estado: str = "pendiente", s=Depends(sesion)):
    exigir(s, "admin_clientes")
    estado = estado if estado in ("pendiente", "unido", "distinto", "todos") else "pendiente"
    r = deduplicacion.listar_pares(estado)
    if r is None:
        return {"instalado": False}
    governance.registrar(s["usuario"], s["rol"], "ver_duplicados", {"origen": "web", "estado": estado}, len(r["pares"]))
    return {"instalado": True, **r}


@app.post("/api/duplicados/sincronizar")
def duplicados_sincronizar(s=Depends(sesion)):
    exigir(s, "admin_clientes")
    with tareas.capturar():
        r = deduplicacion.sincronizar(s["usuario"])
    governance.registrar(s["usuario"], s["rol"], "dedup_sincronizar",
                         {"origen": "web", "fusiones": len(r["fusiones"]), "pendientes": len(r["pendientes"])},
                         len(r["fusiones"]))
    return r


@app.post("/api/duplicados/{id_par}/unir")
def duplicados_unir(id_par: int, s=Depends(sesion)):
    exigir(s, "admin_clientes")
    r = deduplicacion.unir_par(id_par, s["usuario"])
    governance.registrar(s["usuario"], s["rol"], "dedup_unir",
                         {"origen": "web", "id_par": id_par, "clave": r["clave_cliente"]}, 1)
    return r


@app.post("/api/duplicados/{id_par}/distintos")
def duplicados_distintos(id_par: int, s=Depends(sesion)):
    exigir(s, "admin_clientes")
    r = deduplicacion.marcar_distintos(id_par, s["usuario"])
    governance.registrar(s["usuario"], s["rol"], "dedup_distintos", {"origen": "web", "id_par": id_par}, 1)
    return r


class RegistroOrigen(BaseModel):
    id_registro: int


@app.post("/api/clientes/separar")
def clientes_separar(datos: RegistroOrigen, s=Depends(sesion)):
    exigir(s, "admin_clientes")
    r = deduplicacion.separar(datos.id_registro, s["usuario"])
    governance.registrar(s["usuario"], s["rol"], "dedup_separar",
                         {"origen": "web", "id_registro": datos.id_registro, "clave_nueva": r["clave_cliente"]}, 1)
    return r


# ------------------------------------------------------------------ LinkedIn autorizado (admin)
class IdsInteres(BaseModel):
    ids: list[int] = []
    todos: bool = False


def _correr_linkedin(tarea, nombres, usuario):
    return ingesta_linkedin.leer(nombres=nombres or None, tarea=tarea, usuario=usuario)


@app.post("/api/linkedin/leer")
def linkedin_leer(datos: PedidoLectura, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    desc = "LinkedIn: " + (", ".join(datos.nombres) if datos.nombres else "perfiles autorizados")
    t = tareas.lanzar("ingesta_linkedin", desc, s["usuario"], _correr_linkedin, list(datos.nombres), s["usuario"])
    governance.registrar(s["usuario"], s["rol"], "leer_linkedin", {"origen": "web", "nombres": datos.nombres}, 0)
    return {"tarea": t.vista()}


# -------------------------------------------------- actividad con tu sesión (cookies/perfil de Chrome)
# El scraper abre Chrome EN ESTE EQUIPO (donde corre el servidor). Si LinkedIn pide
# login, la tarea se queda esperando a que pulses «Ya inicié sesión» en esta web.
_ESPERAS_LOGIN = {}
_ESPERAS_LOCK = threading.Lock()


class PedidoActividad(BaseModel):
    url: str = Field(min_length=10, max_length=300)
    max_posts: int = Field(default=10, ge=1, le=10)


def _confirmador_login(tarea):
    """Callable que el scraper llama al pedir login: bloquea hasta que el front responda."""
    def confirmar(contexto=""):
        espera = {"evento": threading.Event(), "decision": "cancelar", "contexto": contexto}
        with _ESPERAS_LOCK:
            _ESPERAS_LOGIN[tarea.id] = espera
        print("⏸ Esperando que confirmes en la web que ya iniciaste sesión en Chrome…")
        try:
            espera["evento"].wait(900)          # 15 min para entrar a mano
            return espera["decision"]
        finally:
            with _ESPERAS_LOCK:
                _ESPERAS_LOGIN.pop(tarea.id, None)
    return confirmar


def _adjuntar_mensajes(nombre, url, red, info, guardado, usuario):
    """Tres borradores de prueba para el prospecto. Un fallo aquí no pierde la ficha."""
    productos = (guardado or {}).get("productos_sugeridos") or []
    if not nombre or not productos:
        return []
    try:
        from app import mensajes_prueba
        from app.ingesta_actividad import hechos_desde_info
        return mensajes_prueba.generar(
            nombre, url, red, productos[0], hechos_desde_info(info), usuario)
    except Exception as e:
        print(f"No se pudieron redactar los mensajes de prueba: {e}")
        return []


def _abrir_bot(red, tarea):
    """Abre Chrome con la sesión de esa red. None si no hay login."""
    raiz = FRONT.parent
    login = _confirmador_login(tarea)
    if red == "linkedin":
        from linkedin_activity_scraper import LinkedInActivityScraper
        bot = LinkedInActivityScraper(
            cookie_file=str(raiz / "linkedin_cookies.json"),
            profile_dir=str(raiz / "chrome_linkedin_profile"),
            confirmar_login=login)
    elif red == "facebook":
        from facebook_activity_scraper import FacebookActivityScraper
        bot = FacebookActivityScraper(
            cookie_file=str(raiz / "facebook_cookies.json"),
            profile_dir=str(raiz / "chrome_facebook_profile"),
            confirmar_login=login)
    elif red == "instagram":
        from instagram_activity_scraper import InstagramActivityScraper
        bot = InstagramActivityScraper(
            cookie_file=str(raiz / "instagram_cookies.json"),
            profile_dir=str(raiz / "chrome_instagram_profile"),
            confirmar_login=login)
    elif red == "x":
        from x_activity_scraper import XActivityScraper
        bot = XActivityScraper(
            cookie_file=str(raiz / "x_cookies.json"),
            profile_dir=str(raiz / "chrome_x_profile"),
            confirmar_login=login)
    else:
        return None
    if bot.iniciar_navegador():
        return bot
    bot.cerrar_navegador(preguntar=False)
    return None


def _procesar_con_bot(red, bot, url, max_posts, usuario, redactar=True):
    """Ficha + seguidores/reposts + publicaciones, con el Chrome ya abierto."""
    if red == "linkedin":
        info = bot.extraer_informacion_perfil(url)
        posts = bot.extraer_publicaciones_perfil(url, max_posts=max_posts)
        info = bot.info_perfil.get(url) or info
        ficha = "\n".join(p for p in (
            info.get("titular"), info.get("bio"), info.get("acerca"), info.get("experiencia"),
            info.get("educacion"), info.get("ubicacion"),
            info.get("paginas_seguidas"), info.get("interacciones")) if p)
        info = perfil_redes.aplicar_lo_publicado(
            info, [{"tipo": "publicacion", "texto": ficha}], origen="ficha")
        bot.guardar_cookies()
        bot.analizar_publicaciones(posts)
        bot.imprimir_recomendaciones()
        analisis = bot
    else:
        info = bot.extraer_informacion_perfil(url)
        if info.get("no_disponible") or (red != "facebook" and not info):
            return {"ok": False, "perfil": url, "perfil_info": info or {},
                    "motivo": f"{red} no muestra ese perfil."}
        try:
            posts = bot.extraer_publicaciones(url, max_posts=max_posts)
        except Exception as e:
            print(f"No se leyeron publicaciones de {red}: {e}")
            posts = []
        info = bot.info or info
        bot.analisis.analizar_publicaciones(posts)
        bot.analisis.imprimir_recomendaciones()
        analisis = bot.analisis
    quien = _persona_autorizada(url) or {}
    nombre = (info or {}).get("nombre") or quien.get("nombre") or ""
    quien = {"nombre": nombre, "clave_cliente": quien.get("clave_cliente")}
    guardado = ingesta_actividad.persistir(quien, red, url, info, posts)
    if nombre:
        ingesta_perfiles.registrar_perfil_leido(nombre, red, url, quien.get("clave_cliente"))
    mensajes = _adjuntar_mensajes(nombre, url, red, info, guardado, usuario) if redactar else []
    omitidas = analisis.omitidas_sensibles
    n_omitidas = sum(omitidas.values()) if hasattr(omitidas, "values") else int(omitidas or 0)
    return {
        "ok": True, "perfil": url, "perfil_info": info, "mensajes": mensajes,
        "temas_del_perfil": analisis.resumen.get(url, {}).get("temas_del_perfil", {}),
        "descartadas_antiguas": getattr(analisis, "descartadas_antiguas", 0)
        or getattr(analisis, "ultimas_descartadas", 0),
        "publicaciones": analisis.resumen.get(url, {}).get("publicaciones_extraidas", len(posts)),
        "omitidas_sensibles": n_omitidas,
        "recomendaciones": analisis.recomendaciones,
        "guardado": guardado,
    }


def _correr_sesion(red, tarea, url, max_posts, usuario, informar_avance=True, redactar=True):
    bot = _abrir_bot(red, tarea)
    if not bot:
        return {"ok": False, "perfil": url,
                "motivo": f"No se confirmó el inicio de sesión en {red}."}
    try:
        if informar_avance:
            tarea.avance(0, 1)
        res = _procesar_con_bot(red, bot, url, max_posts, usuario, redactar)
        if informar_avance:
            tarea.avance(1, 1)
        return res
    finally:
        bot.cerrar_navegador(preguntar=False)


def _correr_linkedin_sesion(tarea, url, max_posts, usuario, informar_avance=True, redactar=True):
    return _correr_sesion("linkedin", tarea, url, max_posts, usuario, informar_avance, redactar)


@app.post("/api/linkedin/actividad")
def linkedin_actividad(datos: PedidoActividad, s=Depends(sesion)):
    """Extrae la actividad de UN perfil con tu sesión y devuelve las recomendaciones."""
    exigir(s, "admin_perfiles")
    clasificada = perfil_redes.clasificar_url(datos.url.strip())
    if not clasificada or clasificada[0] != "linkedin":
        raise HTTPException(400, "Indica la URL de un perfil de LinkedIn: https://www.linkedin.com/in/…")
    url = clasificada[1] if clasificada[1].endswith("/") else clasificada[1] + "/"
    t = tareas.lanzar("ingesta_linkedin_sesion", f"Actividad LinkedIn: {url}", s["usuario"],
                      _correr_linkedin_sesion, url, datos.max_posts, s["usuario"])
    governance.registrar(s["usuario"], s["rol"], "leer_linkedin_sesion",
                         {"origen": "web", "url": url, "max_posts": datos.max_posts}, 0)
    return {"tarea": t.vista()}


@app.get("/api/linkedin/actividad/esperas")
def linkedin_esperas(s=Depends(sesion)):
    """Tareas del scraper que están paradas esperando tu login manual en Chrome."""
    exigir(s, "admin_perfiles")
    with _ESPERAS_LOCK:
        ids = list(_ESPERAS_LOGIN)
    return [{"id": i, "contexto": _ESPERAS_LOGIN.get(i, {}).get("contexto", "")}
            for i in ids
            if (t := tareas.obtener(i)) and (t.usuario == s["usuario"] or s["rol"] == "admin")]


def _resolver_espera(id_tarea, decision, s):
    with _ESPERAS_LOCK:
        espera = _ESPERAS_LOGIN.get(id_tarea)
    t = tareas.obtener(id_tarea)
    if not espera or not t or (t.usuario != s["usuario"] and s["rol"] != "admin"):
        raise HTTPException(404, "Esa tarea no está esperando un inicio de sesión.")
    espera["decision"] = decision
    espera["evento"].set()
    return {"ok": True}


@app.post("/api/linkedin/actividad/{id_tarea}/continuar")
def linkedin_continuar(id_tarea: str, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return _resolver_espera(id_tarea, "continuar", s)


@app.post("/api/linkedin/actividad/{id_tarea}/cancelar")
def linkedin_cancelar(id_tarea: str, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return _resolver_espera(id_tarea, "cancelar", s)


# -------------------------------------------------- Facebook con tu sesión (mismo criterio)
def _correr_facebook_sesion(tarea, url, max_posts, usuario, informar_avance=True, redactar=True):
    return _correr_sesion("facebook", tarea, url, max_posts, usuario, informar_avance, redactar)


def _persona_autorizada(url):
    """La persona del archivo de autorizados dueña de esa URL, o None."""
    archivo = ingesta_perfiles.ARCHIVO
    if not archivo.is_file():
        return None
    try:
        data = json.loads(archivo.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    personas, _ = perfil_redes.cargar_autorizados(data if isinstance(data, list) else [])
    clasificada = perfil_redes.clasificar_url(url)
    if not clasificada:
        return None
    red, limpia = clasificada
    for persona in personas:
        for entrada in persona.get("urls") or []:
            if entrada.get("red") == red and entrada.get("url").rstrip("/") == limpia.rstrip("/"):
                return persona
    return None


@app.post("/api/facebook/actividad")
def facebook_actividad(datos: PedidoActividad, s=Depends(sesion)):
    """Extrae ficha, seguidos, publicaciones y reposts de UN perfil de Facebook con tu sesión."""
    exigir(s, "admin_perfiles")
    clasificada = perfil_redes.clasificar_url(datos.url.strip())
    if not clasificada or clasificada[0] != "facebook":
        raise HTTPException(400, "Indica la URL de un perfil de Facebook: https://www.facebook.com/usuario")
    url = clasificada[1]
    t = tareas.lanzar("extraccion_facebook", f"Ficha Facebook: {url}", s["usuario"],
                      _correr_facebook_sesion, url, datos.max_posts, s["usuario"])
    governance.registrar(s["usuario"], s["rol"], "leer_facebook_sesion",
                         {"origen": "web", "url": url, "max_posts": datos.max_posts}, 0)
    return {"tarea": t.vista()}


@app.get("/api/facebook/actividad/esperas")
def facebook_esperas(s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return linkedin_esperas(s)


@app.post("/api/facebook/actividad/{id_tarea}/continuar")
def facebook_continuar(id_tarea: str, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return _resolver_espera(id_tarea, "continuar", s)


@app.post("/api/facebook/actividad/{id_tarea}/cancelar")
def facebook_cancelar(id_tarea: str, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return _resolver_espera(id_tarea, "cancelar", s)


# -------------------------------------------------- página de Facebook (likes y comentarios)
class PedidoPaginaFb(BaseModel):
    url: str = Field(min_length=10, max_length=300)
    max_posts: int = Field(default=5, ge=1, le=10)
    max_personas: int = Field(default=30, ge=1, le=50)


def _correr_facebook_pagina(tarea, url, max_posts, max_personas, usuario):
    bot = _abrir_bot("facebook", tarea)
    if not bot:
        return {"ok": False, "motivo": "No se confirmó el inicio de sesión en Facebook."}
    tarea.bot = bot
    try:
        return bot.extraer_interactuantes_pagina(
            url, max_posts=max_posts, max_personas=max_personas, tarea=tarea)
    finally:
        tarea.bot = None
        bot.cerrar_navegador(preguntar=False)


@app.get("/api/facebook/pagina")
def facebook_pagina_listar(pagina: str = "", s=Depends(sesion)):
    """Personas que ya se leyeron interactuando con una página de Facebook."""
    exigir(s, "admin_perfiles")
    url = facebook_pagina.clasificar_url_pagina(pagina.strip()) if pagina.strip() else None
    if pagina.strip() and not url:
        raise HTTPException(400, "Indica la URL de una página de Facebook.")
    return {
        "personas": facebook_pagina.listar(url),
        "pagina": url or "",
        "pagina_defecto": facebook_pagina.PAGINA_DEFECTO,
    }


class PedidoUrlPagina(BaseModel):
    url: str = Field(min_length=10, max_length=300)
    nombre: str = ""


@app.get("/api/facebook/paginas")
def facebook_paginas_listar(s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return {"paginas": facebook_pagina.listar_paginas(), "pagina_defecto": facebook_pagina.PAGINA_DEFECTO}


@app.post("/api/facebook/paginas")
def facebook_paginas_agregar(datos: PedidoUrlPagina, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    p = facebook_pagina.agregar_pagina(datos.url, datos.nombre)
    if not p:
        raise HTTPException(400, "Indica la URL de una página de Facebook de seguros.")
    return p


@app.delete("/api/facebook/paginas")
def facebook_paginas_quitar(url: str, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    if not facebook_pagina.quitar_pagina(url):
        raise HTTPException(400, "MAPFRE Colombia no se quita. Quita solo las páginas que añadiste.")
    return {"ok": True}


class PedidoRecopilar(BaseModel):
    url: str = ""
    urls: list[str] = []
    nombre: str = ""
    origen: str = ""


@app.get("/api/perfiles/recopilar")
def perfiles_recopilar_listar(s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return {"perfiles": facebook_pagina.listar_recopilar()}


@app.post("/api/perfiles/recopilar")
def perfiles_recopilar_agregar(datos: PedidoRecopilar, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    urls = [u.strip() for u in ([datos.url] + list(datos.urls or [])) if u and str(u).strip()]
    if not urls:
        raise HTTPException(400, "Pega al menos una URL de perfil.")
    agregados, fallidas = [], []
    for u in urls:
        p = facebook_pagina.agregar_recopilar(u, datos.nombre, datos.origen)
        if p:
            agregados.append(p)
        else:
            fallidas.append(u)
    return {"agregados": agregados, "n": len(agregados), "fallidas": fallidas}


@app.delete("/api/perfiles/recopilar")
def perfiles_recopilar_quitar(url: str, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    if not facebook_pagina.quitar_recopilar(url):
        raise HTTPException(404, "Ese perfil no estaba en la lista.")
    return {"ok": True}


@app.post("/api/perfiles/recopilar/desde-pagina")
def perfiles_recopilar_desde_pagina(pagina: str = "", s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    url = facebook_pagina.clasificar_url_pagina(pagina.strip()) if pagina.strip() else None
    n = facebook_pagina.pasar_interactuantes_a_recopilar(url)
    return {"n": n, "perfiles": facebook_pagina.listar_recopilar()}


class PedidoRecopilarLeer(BaseModel):
    max_posts: int = Field(default=5, ge=1, le=10)


@app.post("/api/perfiles/recopilar/leer")
def perfiles_recopilar_leer(datos: PedidoRecopilarLeer, s=Depends(sesion)):
    """Lee interacciones de los perfiles generales (lote de las URLs guardadas)."""
    exigir(s, "admin_perfiles")
    urls = [p["url"] for p in facebook_pagina.listar_recopilar()]
    if not urls:
        raise HTTPException(400, "Añade perfiles a la lista general primero.")
    t = tareas.lanzar("ingesta_lote", f"Recopilar: {len(urls)} perfil(es)", s["usuario"],
                      _correr_lote, urls, datos.max_posts, s["usuario"])
    return {"tarea": t.vista(), "urls": urls, "solo_urls": True}


@app.post("/api/facebook/pagina")
def facebook_pagina_extraer(datos: PedidoPaginaFb, s=Depends(sesion)):
    """Lee likes, comentarios y shares de una página y saca la URL de cada perfil."""
    exigir(s, "admin_perfiles")
    url = facebook_pagina.clasificar_url_pagina(datos.url.strip())
    if not url:
        raise HTTPException(400, "Indica la URL de una página de Facebook: https://www.facebook.com/nombre-de-la-pagina")
    t = tareas.lanzar(
        "extraccion_facebook_pagina",
        f"Página Facebook: {url}",
        s["usuario"],
        _correr_facebook_pagina, url, datos.max_posts, datos.max_personas, s["usuario"])
    governance.registrar(s["usuario"], s["rol"], "leer_facebook_pagina",
                         {"origen": "web", "url": url, "max_posts": datos.max_posts,
                          "max_personas": datos.max_personas}, 0)
    return {"tarea": t.vista(), "pagina": url}


@app.get("/api/facebook/pagina/esperas")
def facebook_pagina_esperas(s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return linkedin_esperas(s)


@app.post("/api/facebook/pagina/{id_tarea}/continuar")
def facebook_pagina_continuar(id_tarea: str, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return _resolver_espera(id_tarea, "continuar", s)


@app.post("/api/facebook/pagina/{id_tarea}/cancelar")
def facebook_pagina_cancelar(id_tarea: str, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return _resolver_espera(id_tarea, "cancelar", s)


# ------------------------------------------------- Instagram con tu sesión (mismo criterio)
def _correr_instagram_sesion(tarea, url, max_posts, usuario, informar_avance=True, redactar=True):
    return _correr_sesion("instagram", tarea, url, max_posts, usuario, informar_avance, redactar)


@app.post("/api/instagram/actividad")
def instagram_actividad(datos: PedidoActividad, s=Depends(sesion)):
    """Extrae ficha + publicaciones del último año de UN perfil de Instagram con tu sesión."""
    exigir(s, "admin_perfiles")
    clasificada = perfil_redes.clasificar_url(datos.url.strip())
    if not clasificada or clasificada[0] != "instagram":
        raise HTTPException(400, "Indica la URL de un perfil de Instagram: https://www.instagram.com/usuario/")
    url = clasificada[1]
    t = tareas.lanzar("extraccion_instagram", f"Actividad Instagram: {url}", s["usuario"],
                      _correr_instagram_sesion, url, datos.max_posts, s["usuario"])
    governance.registrar(s["usuario"], s["rol"], "leer_instagram_sesion",
                         {"origen": "web", "url": url, "max_posts": datos.max_posts}, 0)
    return {"tarea": t.vista()}


@app.get("/api/instagram/actividad/esperas")
def instagram_esperas(s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return linkedin_esperas(s)


@app.post("/api/instagram/actividad/{id_tarea}/continuar")
def instagram_continuar(id_tarea: str, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return _resolver_espera(id_tarea, "continuar", s)


@app.post("/api/instagram/actividad/{id_tarea}/cancelar")
def instagram_cancelar(id_tarea: str, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return _resolver_espera(id_tarea, "cancelar", s)


# ------------------------------------------------------- X con tu sesión (mismo criterio)
def _correr_x_sesion(tarea, url, max_posts, usuario, informar_avance=True, redactar=True):
    return _correr_sesion("x", tarea, url, max_posts, usuario, informar_avance, redactar)


@app.post("/api/x/actividad")
def x_actividad(datos: PedidoActividad, s=Depends(sesion)):
    """Extrae ficha, publicaciones, respuestas y logros de UN perfil de X con tu sesión."""
    exigir(s, "admin_perfiles")
    clasificada = perfil_redes.clasificar_url(datos.url.strip())
    if not clasificada or clasificada[0] != "x":
        raise HTTPException(400, "Indica la URL de un perfil de X: https://x.com/usuario")
    url = clasificada[1]
    t = tareas.lanzar("extraccion_x", f"Actividad X: {url}", s["usuario"],
                      _correr_x_sesion, url, datos.max_posts, s["usuario"])
    governance.registrar(s["usuario"], s["rol"], "leer_x_sesion",
                         {"origen": "web", "url": url, "max_posts": datos.max_posts}, 0)
    return {"tarea": t.vista()}


@app.get("/api/x/actividad/esperas")
def x_esperas(s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return linkedin_esperas(s)


@app.post("/api/x/actividad/{id_tarea}/continuar")
def x_continuar(id_tarea: str, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return _resolver_espera(id_tarea, "continuar", s)


@app.post("/api/x/actividad/{id_tarea}/cancelar")
def x_cancelar(id_tarea: str, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return _resolver_espera(id_tarea, "cancelar", s)


@app.get("/api/linkedin/intereses")
def linkedin_intereses(estado: str = "pendiente", s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    ingesta_linkedin.asegurar_tabla()
    where = {"pendiente": "NOT i.activo AND NOT i.descartado",
             "aprobado": "i.activo",
             "descartado": "i.descartado AND NOT i.activo"}.get(estado, "TRUE")
    return _consulta(f"""SELECT i.id_interes, i.nombre, i.clave_cliente, i.tema, i.producto, i.razon,
                                i.activo, i.descartado, i.fuente_url, i.fecha_actualizacion,
                                COALESCE(i.red, p.red, 'linkedin') AS red, p.texto, p.tiempo
                         FROM public.intereses_linkedin i
                         JOIN public.publicaciones_linkedin p USING (id_publicacion)
                         WHERE {where} ORDER BY i.id_interes DESC LIMIT 200""")


@app.post("/api/linkedin/intereses/aprobar")
def linkedin_aprobar(datos: IdsInteres, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    return _correr_comando(ingesta_linkedin.cmd_aprobar,
                           argparse.Namespace(ids=datos.ids, todos=datos.todos, usuario=s["usuario"]))


@app.post("/api/linkedin/intereses/descartar")
def linkedin_descartar(datos: IdsInteres, s=Depends(sesion)):
    exigir(s, "admin_perfiles")
    if not datos.ids:
        raise HTTPException(400, "Indica los intereses a descartar.")
    return _correr_comando(ingesta_linkedin.cmd_descartar,
                           argparse.Namespace(ids=datos.ids, usuario=s["usuario"]))


# ------------------------------------------------------------------ auditoría (admin)
@app.get("/api/auditoria")
def auditoria(limite: int = 200, usuario: str = "", accion: str = "", s=Depends(sesion)):
    exigir(s, "ver_auditoria")
    columnas = _consulta("""SELECT column_name, data_type FROM information_schema.columns
                            WHERE table_schema = 'public' AND table_name = 'auditoria_consultas'
                            ORDER BY ordinal_position""")
    if not columnas:
        raise HTTPException(404, "No existe la tabla public.auditoria_consultas.")
    orden = next((c["column_name"] for c in columnas if c["data_type"].startswith("timestamp")),
                 columnas[0]["column_name"])
    where, params = ["TRUE"], []
    if usuario.strip():
        where.append("usuario ILIKE %s")
        params.append(f"%{usuario.strip()}%")
    if accion.strip():
        where.append("accion = %s")
        params.append(accion.strip())
    q = sql.SQL("SELECT * FROM public.auditoria_consultas WHERE {w} ORDER BY {o} DESC LIMIT %s").format(
        w=sql.SQL(" AND ".join(where)), o=sql.Identifier(orden))
    filas = _consulta(q, params + [min(max(limite, 1), 1000)])
    acciones = _consulta("SELECT accion, COUNT(*) AS n FROM public.auditoria_consultas GROUP BY 1 ORDER BY 2 DESC")
    return {"filas": filas, "acciones": acciones, "columnas": [c["column_name"] for c in columnas]}


# ------------------------------------------------------------------ front estático (al final: no tapa la API)
app.mount("/", StaticFiles(directory=FRONT, html=True), name="front")


def main():
    import uvicorn
    host = os.getenv("WEB_HOST", "127.0.0.1")
    puerto = int(os.getenv("PORT") or os.getenv("WEB_PUERTO", "8000"))
    print(f"Motor de perfilamiento IA  ->  http://{host}:{puerto}   (Ctrl+C para detener)")
    print("Lote: solo las URLs pegadas. No se leen Personas autorizadas.")
    uvicorn.run(app, host=host, port=puerto)


if __name__ == "__main__":
    main()
