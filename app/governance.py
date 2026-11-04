"""Capa de Gobierno: permisos, minimización y auditoría. Código determinista, NO depende del LLM."""
import json
import os

from app.database import get_connection

_ASESOR = {"contar", "resumen", "mensaje_segmento", "listar",
           "mensaje_cliente", "mensajes_lote", "ver_mensajes", "cambiar_estado"}
PERMISOS = {
    "analista": {"contar", "resumen", "mensaje_segmento"},                    # solo agregados
    "asesor":   _ASESOR,                                                      # puede ver individuos
    "admin":    _ASESOR | {"admin_conocimiento", "admin_perfiles", "admin_clientes",  # + revisión, ingesta,
                           "ver_auditoria"},                                        #   duplicados y auditoría
}
K_MIN = int(os.getenv("K_MIN", "5"))          # grupos con menos de K_MIN personas se suprimen para rol analista
LIMITE_LISTADO = 50


def autorizar(rol, accion):
    return accion in PERMISOS.get(rol, set())


def aplicar_k_anonimato(rows, rol):
    if autorizar(rol, "listar"):      # quien ya puede ver individuos no necesita la supresión
        return rows
    return [(v, n) for v, n in rows if n >= K_MIN]


def registrar(usuario, rol, accion, parametros, filas, resultado="ok"):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.auditoria_consultas "
                "(usuario, rol, accion, parametros, filas, resultado) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (usuario, rol, accion, json.dumps(parametros, ensure_ascii=False), filas, resultado))
        conn.commit()
    finally:
        conn.close()