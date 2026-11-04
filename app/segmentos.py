"""Capa de datos para KPIs. TODAS las cifras salen de SQL, nunca del LLM."""
import os

from psycopg2 import sql

from app.database import get_connection

VISTA = sql.Identifier("public", "clientes_segmentados")

# Lista blanca: el LLM solo puede elegir entre estas columnas.
DIMENSIONES = {
    "segmento", "rango_edad", "ciudad", "profesion", "universidad",
    "producto_interes", "genero", "tiene_universidad", "tiene_correo", "tiene_celular",
}
COLUMNAS_BOOL = {"tiene_universidad", "tiene_correo", "tiene_celular"}
# Campos de texto libre: se busca por coincidencia parcial ("eafit" encuentra "Universidad EAFIT").
TEXTO_PARCIAL = {"ciudad", "profesion", "universidad", "producto_interes"}
COLUMNAS_LISTADO = [
    "clave_cliente", "nombre", "genero", "edad", "rango_edad", "ciudad",
    "profesion", "universidad", "producto_interes", "segmento", "correo", "celular",
]
# Si existe una columna de consentimiento en la view, defínela en .env (CONSENT_COLUMN=...)
CONSENT_COLUMN = os.getenv("CONSENT_COLUMN")


def _singular(valor):
    """Raíz de la palabra: 'ingenieros'/'ingeniera'/'ingeniería' -> 'ingenier'
    (encuentra Ingeniero, Ingeniera, Ingeniería...)."""
    v = str(valor).strip()
    for suf in ("es", "os", "as", "s"):
        if v.lower().endswith(suf) and len(v) - len(suf) >= 4:
            v = v[: -len(suf)]
            break
    for suf in ("ía", "ia", "o", "a"):
        if v.lower().endswith(suf) and len(v) - len(suf) >= 4:
            return v[: -len(suf)]
    return v


def _bool(valor):
    return "true" if str(valor).strip().lower() in {"si", "sí", "true", "yes", "1", "verdadero"} else "false"


def _where(filtros):
    clauses, params = [], []
    for col, val in (filtros or {}).items():
        if col not in DIMENSIONES:
            raise ValueError(f"Filtro no permitido: {col}")
        if col in TEXTO_PARCIAL:
            texto = _singular(val) if col == "profesion" else str(val).strip()
            clauses.append(sql.SQL("{}::text ILIKE %s").format(sql.Identifier(col)))
            params.append(f"%{texto}%")
        elif col in COLUMNAS_BOOL:
            clauses.append(sql.SQL("{}::text = %s").format(sql.Identifier(col)))
            params.append(_bool(val))
        else:
            clauses.append(sql.SQL("LOWER({}::text) = LOWER(%s)").format(sql.Identifier(col)))
            params.append(str(val))
    if not clauses:
        return sql.SQL(""), params
    return sql.SQL("WHERE ") + sql.SQL(" AND ").join(clauses), params


def _fetch(query, params):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            columns_info = cur.description
            if columns_info is None:
                return [], []
            return cur.fetchall(), [d[0] for d in columns_info]
    finally:
        conn.close()


def contar_por(dimension, filtros=None):
    if dimension not in DIMENSIONES:
        raise ValueError(f"Dimensión no permitida: {dimension}")
    where, params = _where(filtros)
    q = sql.SQL("SELECT {d}::text AS valor, COUNT(*) AS n FROM {v} {w} "
                "GROUP BY {d} ORDER BY n DESC").format(
        d=sql.Identifier(dimension), v=VISTA, w=where)
    rows, _ = _fetch(q, params)
    return [(v if v is not None else "sin_dato", n) for v, n in rows]


def listar(filtros=None, limite=50):
    where, params = _where(filtros)
    if CONSENT_COLUMN:
        cons = sql.SQL("{} = TRUE").format(sql.Identifier(CONSENT_COLUMN))
        where = (where + sql.SQL(" AND ") + cons) if params else sql.SQL("WHERE ") + cons
    q = sql.SQL("SELECT {cols} FROM {v} {w} ORDER BY nombre LIMIT %s").format(
        cols=sql.SQL(", ").join(map(sql.Identifier, COLUMNAS_LISTADO)), v=VISTA, w=where)
    rows, cols = _fetch(q, params + [int(limite)])
    return [dict(zip(cols, r)) for r in rows]


def resumen_segmento(filtros):
    """Hechos agregados y explícitos del grupo (sin datos personales)."""
    where, params = _where(filtros)
    total, _ = _fetch(sql.SQL("SELECT COUNT(*), ROUND(AVG(edad)::numeric,1) FROM {v} {w}")
                      .format(v=VISTA, w=where), params)
    resumen = {"total": total[0][0], "edad_promedio": total[0][1]}
    for dim in ("ciudad", "profesion", "producto_interes"):
        resumen[f"top_{dim}"] = contar_por(dim, filtros)[:3]
    return resumen


def contar_total(filtros):
    where, params = _where(filtros)
    rows, _ = _fetch(sql.SQL("SELECT COUNT(*) FROM {v} {w}").format(v=VISTA, w=where), params)
    return rows[0][0]


def diagnostico(filtros):
    """Cuántos registros cumple cada filtro por separado (para entender un resultado vacío)."""
    lineas = [f"  Sin filtros (todos los clientes): {contar_total({})}"]
    for k, v in filtros.items():
        lineas.append(f"  Solo {k} = {v}: {contar_total({k: v})}")
    return "\n".join(lineas)