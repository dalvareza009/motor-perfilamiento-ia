"""Deduplicación de clientes por resolución de entidades (record linkage).

1. Normaliza en SQL (dedup_texto / dedup_correo / dedup_celular): sin tildes, '' = vacío, celular sin el 57.
2. Genera pares candidatos por bloques (mismo correo, mismo celular, nombre parecido) para no comparar todo
   contra todo.
3. Puntúa cada par campo por campo con pesos explicables (estilo Fellegi-Sunter): lo que coincide suma,
   lo que se contradice resta. Desde AUTO se une solo; entre REVISION y AUTO queda para revisión humana.
4. Agrupa de forma transitiva (si A=B y B=C, son uno) respetando los pares marcados como "distintos".
5. Mantiene un registro maestro con llave ESTABLE (clave_cliente = CL000123): no cambia aunque cambien
   el correo o el celular. clientes_consolidados arma un solo perfil por persona, campo por campo.

  python -m app.deduplicacion migrar --simular        prueba completa en una transacción que se revierte
  python -m app.deduplicacion migrar                  instala tablas, vistas y trigger; une y migra las claves
  python -m app.deduplicacion sincronizar             busca duplicados nuevos (p. ej. tras cargar clientes)
  python -m app.deduplicacion pendientes | ver CLAVE | unir ID_PAR | distintos ID_PAR | separar ID_REGISTRO
  python -m app.deduplicacion deshacer --si           vuelve a las vistas y claves anteriores
"""
import argparse
import os
import re
import unicodedata

from psycopg2.extras import Json

from app.database import get_connection

AUTO = float(os.getenv("DEDUP_AUTO", "12"))
REVISION = float(os.getenv("DEDUP_REVISION", "6"))
MAX_BLOQUE = 300          # un bloque más grande (p. ej. un apellido muy común) se omite y se informa

PESOS = {
    "correo_igual": 10, "correo_distinto": -2,
    "celular_igual": 8, "celular_distinto": -2,
    "nombre_igual": 5, "nombre_casi": 4, "nombre_parecido": 2, "nombre_distinto": -5,
    "genero_distinto": -5,
    "edad_igual": 2, "edad_cercana": 1, "edad_lejana": -4,
    "ciudad_igual": 1, "ciudad_distinta": -1,
    "profesion_compatible": 1, "universidad_compatible": 1,
}

VISTAS = ["clientes_limpios", "clientes_con_completitud", "clientes_consolidados",
          "duplicados_detectados", "clientes_segmentados"]      # orden de creación
REFERENCIAS = [("mensajes", "id_mensaje", "clave_cliente"),
               ("perfiles", "id_perfil", "id_cliente_consolidado"),
               ("hechos_perfil", "id_hecho", "clave_cliente")]
PRIORIDAD_MENSAJE = {"aprobado": 0, "borrador": 1, "requiere_revision": 2}


# ================================================================== comparación (lógica pura, sin BD)
VACIAS = {"de", "del", "la", "las", "los", "y", "e", "da", "do", "dos"}
VACIAS_UNIVERSIDAD = VACIAS | {"universidad", "university", "student", "estudiante", "at", "en", "of", "the"}


def _n(texto):
    t = unicodedata.normalize("NFD", str(texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


def _tokens(texto, vacias=VACIAS):
    return [t for t in re.findall(r"[a-z0-9]+", _n(texto)) if t not in vacias]


def jaro_winkler(a, b, p=0.1):
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    rango = max(max(len(a), len(b)) // 2 - 1, 0)
    usados_a, usados_b = [False] * len(a), [False] * len(b)
    m = 0
    for i, ca in enumerate(a):
        for j in range(max(0, i - rango), min(len(b), i + rango + 1)):
            if not usados_b[j] and b[j] == ca:
                usados_a[i] = usados_b[j] = True
                m += 1
                break
    if not m:
        return 0.0
    k = transpuestas = 0
    for i, ca in enumerate(a):
        if usados_a[i]:
            while not usados_b[k]:
                k += 1
            if ca != b[k]:
                transpuestas += 1
            k += 1
    jaro = (m / len(a) + m / len(b) + (m - transpuestas / 2) / m) / 3
    prefijo = 0
    for ca, cb in zip(a[:4], b[:4]):
        if ca != cb:
            break
        prefijo += 1
    return jaro + prefijo * p * (1 - jaro)


def sim_nombre(a, b):
    """0..1 entre dos nombres, sin tildes ni mayúsculas. None si falta alguno."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return None
    if set(ta) == set(tb):
        return 1.0
    candidatos = [jaro_winkler(" ".join(ta), " ".join(tb)),
                  jaro_winkler(" ".join(sorted(ta)), " ".join(sorted(tb)))]
    corto, largo = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if len(corto) >= 2:      # Juan López ~ Juan Manuel López; Jhon Pérez ~ John Pérez
        mejores = [max(jaro_winkler(t, u) for u in largo) for t in corto]
        if min(mejores) >= 0.9:
            candidatos.append(0.88 + 0.1 * len(corto) / len(largo))
    return max(candidatos)


def sim_texto(a, b, vacias=VACIAS):
    """Profesión / universidad: 1.0 si una contiene a la otra ("Diseñadora" ⊂ "Diseñadora gráfica")."""
    ta, tb = set(_tokens(a, vacias)), set(_tokens(b, vacias))
    if not ta or not tb:
        return None
    if ta <= tb or tb <= ta:
        return 1.0
    return max(jaro_winkler(" ".join(sorted(ta)), " ".join(sorted(tb))), len(ta & tb) / len(ta | tb))


def comparar(a, b):
    """-> (puntaje, detalle). Cada línea del detalle explica cuánto sumó o restó un campo."""
    detalle = []

    def suma(campo, peso, motivo):
        detalle.append({"campo": campo, "aporte": PESOS[peso], "motivo": motivo})

    if a.get("correo") and b.get("correo"):
        if a["correo"] == b["correo"]:
            suma("correo", "correo_igual", "mismo correo")
        else:
            suma("correo", "correo_distinto", "correos distintos")
    if a.get("celular") and b.get("celular"):
        if a["celular"] == b["celular"]:
            suma("celular", "celular_igual", "mismo celular")
        else:
            suma("celular", "celular_distinto", "celulares distintos")
    s = sim_nombre(a.get("nombre"), b.get("nombre"))
    if s is not None:
        if s >= 0.97:
            suma("nombre", "nombre_igual", "mismo nombre (sin tildes ni mayúsculas)")
        elif s >= 0.90:
            suma("nombre", "nombre_casi", f"nombre casi igual ({s:.2f})")
        elif s >= 0.80:
            suma("nombre", "nombre_parecido", f"nombre parecido ({s:.2f})")
        elif s < 0.65:
            suma("nombre", "nombre_distinto", f"nombres distintos ({s:.2f})")
    if a.get("genero") and b.get("genero") and _n(a["genero"]) != _n(b["genero"]):
        suma("genero", "genero_distinto", "género distinto")
    if a.get("edad") is not None and b.get("edad") is not None:
        d = abs(int(a["edad"]) - int(b["edad"]))
        if d == 0:
            suma("edad", "edad_igual", "misma edad")
        elif d == 1:
            suma("edad", "edad_cercana", "edad con 1 año de diferencia")
        elif d > 3:
            suma("edad", "edad_lejana", f"edades distintas ({a['edad']} y {b['edad']})")
    if a.get("ciudad") and b.get("ciudad"):
        if _n(a["ciudad"]) == _n(b["ciudad"]):
            suma("ciudad", "ciudad_igual", "misma ciudad")
        else:
            suma("ciudad", "ciudad_distinta", "ciudades distintas")
    s = sim_texto(a.get("profesion"), b.get("profesion"))
    if s is not None and s >= 0.85:
        suma("profesion", "profesion_compatible", "profesión compatible")
    s = sim_texto(a.get("universidad"), b.get("universidad"), VACIAS_UNIVERSIDAD)
    if s is not None and s >= 0.85:
        suma("universidad", "universidad_compatible", "misma universidad")
    return sum(d["aporte"] for d in detalle), detalle


def claves_bloque(r):
    claves = []
    if r.get("correo"):
        claves.append("c:" + r["correo"])
    if r.get("celular"):
        claves.append("t:" + r["celular"])
    t = _tokens(r.get("nombre"))
    if t:
        claves += [f"n:{t[0]}|{u}" for u in t[1:]] or [f"n:{t[0]}"]
        if len(t) > 1 and r.get("ciudad"):
            claves.append(f"a:{t[0][0]}|{t[-1]}|{_n(r['ciudad'])}")
    return claves


def pares_candidatos(registros):
    """-> (pares (id_menor, id_mayor), bloques omitidos por grandes)."""
    bloques = {}
    for r in registros:
        for k in claves_bloque(r):
            bloques.setdefault(k, set()).add(r["id_registro"])
    pares, omitidos = set(), []
    for k, ids in bloques.items():
        if len(ids) > MAX_BLOQUE:
            omitidos.append((k, len(ids)))
            continue
        orden = sorted(ids)
        for i, a in enumerate(orden):
            for b in orden[i + 1:]:
                pares.add((a, b))
    return pares, omitidos


class Grupos:
    """Registro -> cliente, con uniones que respetan los pares marcados como distintos."""

    def __init__(self, asignacion):
        self.de = dict(asignacion)
        self.miembros = {}
        for r, c in self.de.items():
            self.miembros.setdefault(c, set()).add(r)

    def puede_unir(self, ca, cb, prohibidos):
        return not any(frozenset((x, y)) in prohibidos for x in self.miembros[ca] for y in self.miembros[cb])

    def unir(self, destino, origen):
        for r in self.miembros.pop(origen):
            self.de[r] = destino
            self.miembros[destino].add(r)


# ================================================================== SQL
DDL = r"""
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;

CREATE OR REPLACE FUNCTION public.dedup_texto(t text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $f$
  SELECT NULLIF(btrim(regexp_replace(lower(public.unaccent('public.unaccent'::regdictionary, coalesce(t, ''))),
                                     '\s+', ' ', 'g')), '')
$f$;

CREATE OR REPLACE FUNCTION public.dedup_correo(t text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $f$
  SELECT CASE WHEN lower(btrim(t)) ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' THEN lower(btrim(t)) END
$f$;

CREATE OR REPLACE FUNCTION public.dedup_celular(t text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $f$
  SELECT CASE WHEN length(d) BETWEEN 10 AND 15 THEN d END
  FROM (SELECT CASE WHEN x ~ '^57\d{10}$' THEN substr(x, 3) ELSE x END AS d
        FROM (SELECT regexp_replace(coalesce(t, ''), '\D', '', 'g') AS x) s) n
$f$;

CREATE TABLE IF NOT EXISTS public.cliente_maestro (
    id_cliente SERIAL PRIMARY KEY,
    clave_cliente TEXT GENERATED ALWAYS AS ('CL' || lpad(id_cliente::text, 6, '0')) STORED UNIQUE,
    fusionado_en INTEGER REFERENCES public.cliente_maestro (id_cliente),
    creado TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.cliente_registro (
    id_registro INTEGER PRIMARY KEY REFERENCES public.clientes (id_registro) ON DELETE CASCADE,
    id_cliente INTEGER NOT NULL REFERENCES public.cliente_maestro (id_cliente),
    metodo TEXT NOT NULL,
    puntaje NUMERIC,
    detalle JSONB,
    decidido_por TEXT,
    fecha TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_cliente_registro_cliente ON public.cliente_registro (id_cliente);

CREATE TABLE IF NOT EXISTS public.par_duplicado (
    id_par SERIAL PRIMARY KEY,
    id_registro_a INTEGER NOT NULL REFERENCES public.clientes (id_registro) ON DELETE CASCADE,
    id_registro_b INTEGER NOT NULL REFERENCES public.clientes (id_registro) ON DELETE CASCADE,
    puntaje NUMERIC NOT NULL,
    detalle JSONB,
    estado TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'unido', 'distinto')),
    decidido_por TEXT,
    fecha_decision TIMESTAMPTZ,
    creado TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (id_registro_a < id_registro_b),
    UNIQUE (id_registro_a, id_registro_b)
);

CREATE TABLE IF NOT EXISTS public.dedup_respaldo (
    id SERIAL PRIMARY KEY,
    tipo TEXT NOT NULL,
    objeto TEXT NOT NULL,
    llave TEXT,
    valor_anterior TEXT,
    fila JSONB,
    operacion TEXT,
    fecha TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION public.dedup_nuevo_registro() RETURNS trigger LANGUAGE plpgsql AS $f$
DECLARE nuevo INTEGER;
BEGIN
  INSERT INTO public.cliente_maestro DEFAULT VALUES RETURNING id_cliente INTO nuevo;
  INSERT INTO public.cliente_registro (id_registro, id_cliente, metodo) VALUES (NEW.id_registro, nuevo, 'nuevo');
  RETURN NEW;
END
$f$;
DROP TRIGGER IF EXISTS trg_dedup_nuevo_registro ON public.clientes;
CREATE TRIGGER trg_dedup_nuevo_registro AFTER INSERT ON public.clientes
  FOR EACH ROW EXECUTE FUNCTION public.dedup_nuevo_registro();
"""


def _limpio(col):
    return f"initcap(NULLIF(btrim(regexp_replace({col}, '\\s+', ' ', 'g')), '')) AS {col}"


def _reciente(col, desempate=""):
    """El dato más reciente no vacío del grupo (empate: el registro más nuevo)."""
    return (f"(array_agg(b.{col} ORDER BY b.fecha_registro DESC NULLS LAST{desempate}, b.id_registro DESC) "
            f"FILTER (WHERE b.{col} IS NOT NULL))[1] AS {col}")


VISTAS_SQL = {
    "clientes_limpios": f"""
CREATE VIEW public.clientes_limpios AS
SELECT id_registro,
       public.dedup_texto(nombre) AS nombre_normalizado,
       initcap(NULLIF(btrim(regexp_replace(nombre, '\\s+', ' ', 'g')), '')) AS nombre_limpio,
       initcap(NULLIF(btrim(genero), '')) AS genero,
       edad,
       public.dedup_correo(correo) AS correo,
       public.dedup_celular(celular) AS celular,
       {_limpio('ciudad')},
       NULLIF(btrim(rango_salarial), '') AS rango_salarial,
       {_limpio('profesion')}, {_limpio('universidad')}, {_limpio('medio')}, {_limpio('tipo_base')},
       {_limpio('producto_interes')},
       fecha_registro
FROM public.clientes""",

    "clientes_con_completitud": """
CREATE VIEW public.clientes_con_completitud AS
SELECT l.*,
       (nombre_limpio IS NOT NULL)::int + (genero IS NOT NULL)::int + (edad IS NOT NULL)::int
     + (correo IS NOT NULL)::int + (celular IS NOT NULL)::int + (ciudad IS NOT NULL)::int
     + (rango_salarial IS NOT NULL)::int + (profesion IS NOT NULL)::int + (universidad IS NOT NULL)::int
     + (medio IS NOT NULL)::int + (tipo_base IS NOT NULL)::int + (producto_interes IS NOT NULL)::int
       AS nivel_completitud
FROM public.clientes_limpios l""",

    # Un perfil por persona, campo por campo: el nombre mejor escrito, y para el resto el dato más reciente
    # (en profesión y universidad, a igual fecha, el más específico).
    "clientes_consolidados": f"""
CREATE VIEW public.clientes_consolidados AS
WITH b AS (
  SELECT m.id_cliente, m.clave_cliente, l.*,
         (l.nombre_limpio IS DISTINCT FROM public.unaccent(l.nombre_limpio)) AS con_tildes
  FROM public.cliente_registro r
  JOIN public.cliente_maestro m ON m.id_cliente = r.id_cliente AND m.fusionado_en IS NULL
  JOIN public.clientes_limpios l ON l.id_registro = r.id_registro
)
SELECT b.clave_cliente,
       MIN(b.id_registro) AS id_registro_origen,
       (array_agg(b.nombre_limpio ORDER BY b.con_tildes DESC, length(b.nombre_limpio) DESC,
                  b.fecha_registro DESC NULLS LAST, b.id_registro DESC)
          FILTER (WHERE b.nombre_limpio IS NOT NULL))[1] AS nombre,
       {_reciente('genero')}, {_reciente('edad')}, {_reciente('correo')}, {_reciente('celular')},
       {_reciente('ciudad')}, {_reciente('rango_salarial')},
       {_reciente('profesion', ', length(b.profesion) DESC')},
       {_reciente('universidad', ', length(b.universidad) DESC')},
       {_reciente('medio')}, {_reciente('tipo_base')}, {_reciente('producto_interes')},
       b.id_cliente,
       COUNT(*) AS n_registros,
       array_agg(b.id_registro ORDER BY b.id_registro) AS registros,
       array_agg(DISTINCT b.correo) FILTER (WHERE b.correo IS NOT NULL) AS correos,
       array_agg(DISTINCT b.celular) FILTER (WHERE b.celular IS NOT NULL) AS celulares,
       array_agg(DISTINCT b.producto_interes) FILTER (WHERE b.producto_interes IS NOT NULL) AS productos_interes
FROM b
GROUP BY b.id_cliente, b.clave_cliente""",

    "duplicados_detectados": """
CREATE VIEW public.duplicados_detectados AS
SELECT p.id_par, p.estado, p.puntaje,
       p.id_registro_a AS id_registro_1, p.id_registro_b AS id_registro_2,
       a.nombre_limpio AS nombre_1, b.nombre_limpio AS nombre_2,
       a.correo AS correo_1, b.correo AS correo_2, a.celular AS celular_1, b.celular AS celular_2,
       a.ciudad AS ciudad_1, b.ciudad AS ciudad_2, a.edad AS edad_1, b.edad AS edad_2,
       p.detalle, p.decidido_por, p.fecha_decision
FROM public.par_duplicado p
JOIN public.clientes_limpios a ON a.id_registro = p.id_registro_a
JOIN public.clientes_limpios b ON b.id_registro = p.id_registro_b""",

    "clientes_segmentados": """
CREATE VIEW public.clientes_segmentados AS
SELECT clave_cliente, nombre, genero, edad, ciudad, profesion, universidad, producto_interes,
       CASE WHEN edad IS NULL THEN 'sin_dato' WHEN edad < 25 THEN '18-24' WHEN edad < 35 THEN '25-34'
            WHEN edad < 45 THEN '35-44' WHEN edad < 55 THEN '45-54' WHEN edad < 65 THEN '55-64'
            ELSE '65+' END AS rango_edad,
       NULLIF(btrim(universidad), '') IS NOT NULL AS tiene_universidad,
       CASE WHEN edad IS NULL OR NULLIF(btrim(producto_interes), '') IS NULL THEN 'sin_clasificar'
            ELSE (CASE WHEN edad < 25 THEN '18-24' WHEN edad < 35 THEN '25-34' WHEN edad < 45 THEN '35-44'
                       WHEN edad < 55 THEN '45-54' WHEN edad < 65 THEN '55-64' ELSE '65+' END)
                 || ' | ' || lower(btrim(producto_interes)) END AS segmento,
       correo,
       correo IS NOT NULL AND btrim(correo) LIKE '%_@_%._%' AS tiene_correo,
       celular,
       length(regexp_replace(coalesce(celular, ''), '\\D', '', 'g')) >= 10 AS tiene_celular,
       id_cliente, n_registros, correos, celulares, productos_interes
FROM public.clientes_consolidados""",
}


# ================================================================== utilidades de BD
def instalado(cur):
    cur.execute("SELECT to_regclass('public.cliente_registro') IS NOT NULL")
    return cur.fetchone()[0]


def _existe(cur, tabla):
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{tabla}",))
    return cur.fetchone()[0]


def _referencias(cur):
    return [(t, pk, col) for t, pk, col in REFERENCIAS if _existe(cur, t)]


def _respaldar(cur, tipo, objeto, llave=None, valor=None, fila=None, operacion=None):
    cur.execute("""INSERT INTO public.dedup_respaldo (tipo, objeto, llave, valor_anterior, fila, operacion)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (tipo, objeto, None if llave is None else str(llave), valor,
                 Json(fila) if fila is not None else None, operacion))


def _asegurar_asignacion(cur, metodo="nuevo"):
    """Todo registro de clientes queda en un cliente maestro (los que no tenían, como cliente propio)."""
    cur.execute("""SELECT c.id_registro FROM public.clientes c
                   LEFT JOIN public.cliente_registro r USING (id_registro)
                   WHERE r.id_registro IS NULL ORDER BY c.id_registro""")
    ids = [f[0] for f in cur.fetchall()]
    for id_registro in ids:
        cur.execute("INSERT INTO public.cliente_maestro DEFAULT VALUES RETURNING id_cliente")
        cur.execute("INSERT INTO public.cliente_registro (id_registro, id_cliente, metodo) VALUES (%s,%s,%s)",
                    (id_registro, cur.fetchone()[0], metodo))
    return len(ids)


def _registros(cur, ids=None):
    cur.execute("""SELECT l.id_registro, l.nombre_limpio AS nombre, l.genero, l.edad, l.correo, l.celular,
                          l.ciudad, l.profesion, l.universidad, l.producto_interes, l.medio, l.fecha_registro,
                          r.id_cliente, m.clave_cliente
                   FROM public.clientes_limpios l
                   JOIN public.cliente_registro r USING (id_registro)
                   JOIN public.cliente_maestro m ON m.id_cliente = r.id_cliente
                   WHERE %s::int[] IS NULL OR l.id_registro = ANY(%s::int[])""", (ids, ids))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, f)) for f in cur.fetchall()]


def _decisiones(cur):
    cur.execute("SELECT id_registro_a, id_registro_b, estado FROM public.par_duplicado")
    return {(a, b): e for a, b, e in cur.fetchall()}


def _guardar_par(cur, a, b, puntaje, detalle, estado, decidido_por=None, forzar=False):
    """Upsert del par. Sin forzar, una decisión ya tomada (unido / distinto) no se cambia."""
    a, b = min(a, b), max(a, b)
    condicion = "TRUE" if forzar else "par_duplicado.estado = 'pendiente'"
    cur.execute(f"""
        INSERT INTO public.par_duplicado (id_registro_a, id_registro_b, puntaje, detalle, estado, decidido_por,
                                          fecha_decision)
        VALUES (%s, %s, %s, %s, %s, %s, CASE WHEN %s = 'pendiente' THEN NULL ELSE now() END)
        ON CONFLICT (id_registro_a, id_registro_b) DO UPDATE SET
          puntaje = EXCLUDED.puntaje, detalle = EXCLUDED.detalle,
          estado = CASE WHEN {condicion} THEN EXCLUDED.estado ELSE par_duplicado.estado END,
          decidido_por = CASE WHEN {condicion} THEN EXCLUDED.decidido_por ELSE par_duplicado.decidido_por END,
          fecha_decision = CASE WHEN {condicion} THEN EXCLUDED.fecha_decision ELSE par_duplicado.fecha_decision END""",
                (a, b, puntaje, Json(detalle), estado, decidido_por, estado))


def _reasignar_clave(cur, vieja, nueva, operacion):
    """Mueve mensajes, perfiles y hechos de una clave a otra. Respeta 'un perfil por cliente' y 'un borrador
    activo por cliente, producto y canal': lo que sobra se respalda (perfil) o se descarta (borrador)."""
    avisos, movidas = [], 0
    if not vieja or vieja == nueva:
        return avisos, movidas
    refs = {t for t, _, _ in _referencias(cur)}
    if "perfiles" in refs:
        cur.execute("""SELECT id_perfil FROM public.perfiles WHERE id_cliente_consolidado IN (%s, %s)
                       ORDER BY fecha_actualizacion DESC NULLS LAST, id_perfil DESC""", (vieja, nueva))
        sobrantes = [f[0] for f in cur.fetchall()][1:]
        for id_perfil in sobrantes:
            cur.execute("SELECT row_to_json(p) FROM public.perfiles p WHERE id_perfil = %s", (id_perfil,))
            _respaldar(cur, "fila", "perfiles", id_perfil, fila=cur.fetchone()[0], operacion=operacion)
            cur.execute("DELETE FROM public.perfiles WHERE id_perfil = %s", (id_perfil,))
            avisos.append(f"Perfil IA #{id_perfil} reemplazado por el más reciente del cliente unificado (respaldado).")
    if "mensajes" in refs:
        cur.execute("""SELECT id_mensaje, lower(producto), canal, estado, fecha_creacion FROM public.mensajes
                       WHERE clave_cliente IN (%s, %s) AND estado IN ('borrador', 'requiere_revision', 'aprobado')""",
                    (vieja, nueva))
        por_grupo = {}
        for m in cur.fetchall():
            por_grupo.setdefault((m[1], m[2]), []).append(m)
        for (producto, canal), ms in por_grupo.items():
            ms.sort(key=lambda m: (PRIORIDAD_MENSAJE[m[3]], -m[4].timestamp()))
            for m in ms[1:]:
                _respaldar(cur, "estado_mensaje", "mensajes", m[0], m[3], operacion=operacion)
                cur.execute("""UPDATE public.mensajes SET estado = 'descartado', revisado_por = 'deduplicacion',
                               fecha_estado = now() WHERE id_mensaje = %s""", (m[0],))
                avisos.append(f"Borrador #{m[0]} descartado: el cliente unificado ya tenía otro activo "
                              f"para {producto} por {canal} (#{ms[0][0]}).")
    for tabla, pk, col in _referencias(cur):
        cur.execute(f"SELECT {pk} FROM public.{tabla} WHERE {col} = %s", (vieja,))
        ids = [f[0] for f in cur.fetchall()]
        for i in ids:
            _respaldar(cur, "clave", f"{tabla}.{pk}.{col}", i, vieja, operacion=operacion)
        if ids:
            cur.execute(f"UPDATE public.{tabla} SET {col} = %s WHERE {col} = %s", (nueva, vieja))
            movidas += len(ids)
    return avisos, movidas


def _fusionar(cur, destino, origen, usuario, operacion, metodo, puntaje=None, detalle=None):
    cur.execute("SELECT id_cliente, clave_cliente FROM public.cliente_maestro WHERE id_cliente IN (%s, %s)",
                (destino, origen))
    claves = dict(cur.fetchall())
    cur.execute("""UPDATE public.cliente_registro SET id_cliente = %s, metodo = %s, puntaje = %s, detalle = %s,
                          decidido_por = %s, fecha = now()
                   WHERE id_cliente = %s""",
                (destino, metodo, puntaje, Json(detalle) if detalle else None, usuario, origen))
    cur.execute("UPDATE public.cliente_maestro SET fusionado_en = %s, actualizado = now() WHERE id_cliente = %s",
                (destino, origen))
    cur.execute("UPDATE public.cliente_maestro SET fusionado_en = %s WHERE fusionado_en = %s", (destino, origen))
    cur.execute("UPDATE public.cliente_maestro SET actualizado = now() WHERE id_cliente = %s", (destino,))
    return _reasignar_clave(cur, claves[origen], claves[destino], operacion)


# ================================================================== sincronización
def _sincronizar(cur, usuario, operacion):
    asignados = _asegurar_asignacion(cur)
    regs = _registros(cur)
    por_id = {r["id_registro"]: r for r in regs}
    decisiones = _decisiones(cur)
    prohibidos = {frozenset(k) for k, e in decisiones.items() if e == "distinto"}
    grupos = Grupos({r["id_registro"]: r["id_cliente"] for r in regs})
    pares, omitidos = pares_candidatos(regs)

    evaluados = []
    for a, b in pares:
        puntaje, detalle = comparar(por_id[a], por_id[b])
        if puntaje >= REVISION:
            evaluados.append((puntaje, a, b, detalle))
    evaluados.sort(key=lambda x: (-x[0], x[1], x[2]))

    fusiones, pendientes, avisos, vigentes = [], [], [], set()
    for puntaje, a, b, detalle in evaluados:
        vigentes.add((a, b))
        if decisiones.get((a, b)) == "distinto":
            continue
        ca, cb = grupos.de[a], grupos.de[b]
        if ca == cb:
            _guardar_par(cur, a, b, puntaje, detalle, "unido", "automatico")
            continue
        if puntaje >= AUTO and grupos.puede_unir(ca, cb, prohibidos):
            destino, origen = min(ca, cb), max(ca, cb)
            av, _ = _fusionar(cur, destino, origen, usuario, operacion, "automatico", puntaje, detalle)
            avisos += av
            grupos.unir(destino, origen)
            _guardar_par(cur, a, b, puntaje, detalle, "unido", "automatico")
            fusiones.append({"registros": [a, b], "nombres": [por_id[a]["nombre"], por_id[b]["nombre"]],
                             "puntaje": puntaje, "detalle": detalle})
        else:
            _guardar_par(cur, a, b, puntaje, detalle, "pendiente")
            pendientes.append({"registros": [a, b], "nombres": [por_id[a]["nombre"], por_id[b]["nombre"]],
                               "puntaje": puntaje})
    # Un pendiente que ya no alcanza el umbral (porque cambiaron los datos) deja de proponerse.
    cur.execute("SELECT id_par, id_registro_a, id_registro_b FROM public.par_duplicado WHERE estado = 'pendiente'")
    viejos = [i for i, a, b in cur.fetchall() if (a, b) not in vigentes]
    if viejos:
        cur.execute("DELETE FROM public.par_duplicado WHERE id_par = ANY(%s)", (viejos,))
    cur.execute("SELECT COUNT(*) FROM public.cliente_maestro m WHERE fusionado_en IS NULL AND EXISTS "
                "(SELECT 1 FROM public.cliente_registro r WHERE r.id_cliente = m.id_cliente)")
    return {"registros": len(regs), "clientes": cur.fetchone()[0], "pares_evaluados": len(pares),
            "nuevos_asignados": asignados, "fusiones": fusiones, "pendientes": pendientes,
            "avisos": avisos, "bloques_omitidos": omitidos, "umbral_auto": AUTO, "umbral_revision": REVISION}


def sincronizar(usuario="sistema", simular=False):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if not instalado(cur):
                raise RuntimeError("La deduplicación no está instalada. Ejecuta: python -m app.deduplicacion migrar")
            reporte = _sincronizar(cur, usuario, "sincronizar")
        conn.rollback() if simular else conn.commit()
        return reporte
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ================================================================== migración y reversa
def _foto(cur):
    """Estado comparable: definiciones de vistas, referencias y estados de borradores."""
    vistas = {}
    for v in VISTAS:
        if _existe(cur, v):
            cur.execute("SELECT pg_get_viewdef(%s::regclass, true)", (f"public.{v}",))
            vistas[v] = cur.fetchone()[0]
    refs = []
    for tabla, pk, col in _referencias(cur):
        cur.execute(f"SELECT {pk}, {col} FROM public.{tabla} ORDER BY {pk}")
        refs += [(tabla, i, c) for i, c in cur.fetchall()]
    estados = []
    if _existe(cur, "mensajes"):
        cur.execute("SELECT id_mensaje, estado FROM public.mensajes ORDER BY 1")
        estados = cur.fetchall()
    return {"vistas": vistas, "referencias": refs, "estados_mensaje": estados}


def _claves_antiguas(cur):
    """La clave que calculaba la vista anterior: correo, si no celular, si no id_registro."""
    cur.execute("""SELECT id_registro,
                          COALESCE(NULLIF(lower(btrim(correo)), ''),
                                   NULLIF(regexp_replace(celular::text, '[^0-9]', '', 'g'), ''),
                                   id_registro::text)
                   FROM public.clientes""")
    return dict(cur.fetchall())


def _recrear_vistas(cur):
    for v in reversed(VISTAS):      # sin CASCADE: si otra vista depende de estas, falla y no se pierde nada
        cur.execute(f"DROP VIEW IF EXISTS public.{v}")
    for v in VISTAS:
        cur.execute(VISTAS_SQL[v])


def _migrar_claves(cur, antiguas, operacion):
    """Pasa las referencias de la clave vieja (correo / celular / id) a la clave estable CL######."""
    cur.execute("""SELECT r.id_registro, m.clave_cliente, l.correo, l.celular
                   FROM public.cliente_registro r JOIN public.cliente_maestro m USING (id_cliente)
                   JOIN public.clientes_limpios l USING (id_registro)""")
    mapa = {}
    for id_registro, clave, correo, celular in cur.fetchall():
        for vieja in {antiguas.get(id_registro), str(id_registro), correo, celular}:
            if vieja:
                mapa.setdefault(vieja, set()).add(clave)
    nuevas = {c for cs in mapa.values() for c in cs}
    valores = set()
    for tabla, _, col in _referencias(cur):
        cur.execute(f"SELECT DISTINCT {col} FROM public.{tabla} WHERE {col} IS NOT NULL AND {col} <> ''")
        valores |= {f[0] for f in cur.fetchall()}
    movidas, ambiguas, sin_cliente, avisos = [], [], [], []
    for vieja in sorted(valores - nuevas):
        destinos = mapa.get(vieja, set())
        if len(destinos) > 1:
            ambiguas.append({"clave": vieja, "clientes": sorted(destinos)})
        elif not destinos:
            sin_cliente.append(vieja)
        else:
            nueva = next(iter(destinos))
            av, n = _reasignar_clave(cur, vieja, nueva, operacion)
            avisos += av
            movidas.append({"de": vieja, "a": nueva, "filas": n})
    return {"movidas": movidas, "ambiguas": ambiguas, "sin_cliente": sin_cliente, "avisos": avisos}


def migrar(usuario="sistema", simular=False, probar_deshacer=False):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            ya = instalado(cur)
            antes = _foto(cur)
            antiguas = None if ya else _claves_antiguas(cur)
            cur.execute(DDL)
            if not ya:                    # las definiciones originales, para poder deshacer
                for v, definicion in antes["vistas"].items():
                    _respaldar(cur, "vista", v, valor=definicion, operacion="migracion")
            asignados = _asegurar_asignacion(cur, "migracion")
            _recrear_vistas(cur)
            reporte = _sincronizar(cur, usuario, "migracion")
            reporte["nuevos_asignados"] = asignados
            reporte["ya_estaba_instalado"] = ya
            reporte["claves"] = _migrar_claves(cur, antiguas, "migracion") if antiguas is not None else None
            cur.execute("SELECT COUNT(*) FROM public.clientes_segmentados")
            reporte["clientes_segmentados"] = cur.fetchone()[0]
            if probar_deshacer and not ya:
                _deshacer(cur)
                despues = _foto(cur)
                reporte["prueba_deshacer"] = {
                    "vistas_iguales": despues["vistas"] == antes["vistas"],
                    "referencias_iguales": despues["referencias"] == antes["referencias"],
                    "estados_iguales": despues["estados_mensaje"] == antes["estados_mensaje"],
                }
        if simular:
            conn.rollback()
        else:
            conn.commit()
        return reporte
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _deshacer(cur):
    """Revierte en orden inverso lo respaldado, mapea claves CL creadas después y restaura las vistas."""
    # Claves CL que quedaron en datos creados después de migrar -> clave antigua del registro de origen.
    cur.execute("""SELECT m.clave_cliente, MIN(r.id_registro) FROM public.cliente_maestro m
                   JOIN public.cliente_registro r ON r.id_cliente = m.id_cliente GROUP BY 1""")
    origen = dict(cur.fetchall())
    cur.execute("SELECT id_cliente, clave_cliente, fusionado_en FROM public.cliente_maestro")
    maestros = {i: (c, f) for i, c, f in cur.fetchall()}
    antiguas = _claves_antiguas(cur)

    cur.execute("SELECT id, tipo, objeto, llave, valor_anterior, fila FROM public.dedup_respaldo "
                "WHERE tipo <> 'vista' ORDER BY id DESC")
    for _, tipo, objeto, llave, valor, fila in cur.fetchall():
        if tipo == "clave":
            tabla, pk, col = objeto.split(".")
            cur.execute(f"UPDATE public.{tabla} SET {col} = %s WHERE {pk} = %s", (valor, int(llave)))
        elif tipo == "estado_mensaje":
            cur.execute("UPDATE public.mensajes SET estado = %s WHERE id_mensaje = %s", (valor, int(llave)))
        elif tipo == "fila" and objeto == "perfiles":
            cur.execute("INSERT INTO public.perfiles SELECT * FROM json_populate_record(NULL::public.perfiles, %s)",
                        (Json(fila),))

    def clave_antigua(clave):
        id_cliente = next((i for i, (c, _) in maestros.items() if c == clave), None)
        while id_cliente is not None and maestros[id_cliente][1]:
            id_cliente = maestros[id_cliente][1]
        destino = maestros[id_cliente][0] if id_cliente else None
        return antiguas.get(origen.get(destino)) if destino in origen else None

    for tabla, _, col in _referencias(cur):
        cur.execute(f"SELECT DISTINCT {col} FROM public.{tabla} WHERE {col} ~ '^CL[0-9]{{6}}$'")
        for (clave,) in cur.fetchall():
            vieja = clave_antigua(clave)
            if vieja:
                cur.execute(f"UPDATE public.{tabla} SET {col} = %s WHERE {col} = %s", (vieja, clave))

    cur.execute("SELECT objeto, valor_anterior FROM public.dedup_respaldo WHERE tipo = 'vista'")
    definiciones = dict(cur.fetchall())
    for v in reversed(VISTAS):
        cur.execute(f"DROP VIEW IF EXISTS public.{v}")
    for v in VISTAS:
        if v in definiciones:
            cur.execute(f"CREATE VIEW public.{v} AS {definiciones[v]}")
    cur.execute("""DROP TRIGGER IF EXISTS trg_dedup_nuevo_registro ON public.clientes;
                   DROP FUNCTION IF EXISTS public.dedup_nuevo_registro();
                   DROP TABLE IF EXISTS public.par_duplicado, public.cliente_registro, public.cliente_maestro,
                                        public.dedup_respaldo;
                   DROP FUNCTION IF EXISTS public.dedup_texto(text), public.dedup_correo(text),
                                           public.dedup_celular(text);""")


def deshacer():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if not instalado(cur):
                raise RuntimeError("No hay nada que deshacer: la deduplicación no está instalada.")
            _deshacer(cur)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ================================================================== decisiones humanas
def _cliente_de(cur, id_registro):
    cur.execute("SELECT id_cliente FROM public.cliente_registro WHERE id_registro = %s", (id_registro,))
    fila = cur.fetchone()
    if not fila:
        raise ValueError(f"El registro {id_registro} no existe.")
    return fila[0]


def _par(cur, id_par):
    cur.execute("SELECT id_registro_a, id_registro_b, puntaje, detalle, estado FROM public.par_duplicado "
                "WHERE id_par = %s", (id_par,))
    fila = cur.fetchone()
    if not fila:
        raise ValueError(f"No existe el par {id_par}.")
    return fila


def _transaccion(fn):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            resultado = fn(cur)
        conn.commit()
        return resultado
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _unir_par(cur, id_par, usuario):
    a, b, puntaje, detalle, _ = _par(cur, id_par)
    ca, cb = _cliente_de(cur, a), _cliente_de(cur, b)
    avisos = []
    if ca != cb:
        cur.execute("SELECT id_registro FROM public.cliente_registro WHERE id_cliente IN (%s, %s)", (ca, cb))
        miembros = [f[0] for f in cur.fetchall()]
        cur.execute("""SELECT id_registro_a, id_registro_b FROM public.par_duplicado
                       WHERE estado = 'distinto' AND id_registro_a = ANY(%s) AND id_registro_b = ANY(%s)
                         AND id_par <> %s""", (miembros, miembros, id_par))
        choque = cur.fetchone()
        if choque:
            raise ValueError(f"Los registros {choque[0]} y {choque[1]} de estos grupos están marcados como "
                             "personas distintas. Revisa esa decisión antes de unir.")
        avisos, _ = _fusionar(cur, min(ca, cb), max(ca, cb), usuario, f"manual:par{id_par}", "manual",
                              puntaje, detalle)
    _guardar_par(cur, a, b, puntaje, detalle, "unido", usuario, forzar=True)
    cur.execute("SELECT clave_cliente FROM public.cliente_maestro WHERE id_cliente = %s", (min(ca, cb),))
    return {"clave_cliente": cur.fetchone()[0], "avisos": avisos}


def unir_par(id_par, usuario):
    return _transaccion(lambda cur: _unir_par(cur, id_par, usuario))


def _separar(cur, id_registro, usuario):
    actual = _cliente_de(cur, id_registro)
    cur.execute("SELECT id_registro FROM public.cliente_registro WHERE id_cliente = %s AND id_registro <> %s",
                (actual, id_registro))
    otros = [f[0] for f in cur.fetchall()]
    if not otros:
        raise ValueError("Ese registro ya es un cliente aparte.")
    cur.execute("INSERT INTO public.cliente_maestro DEFAULT VALUES RETURNING id_cliente, clave_cliente")
    nuevo, clave = cur.fetchone()
    cur.execute("""UPDATE public.cliente_registro SET id_cliente = %s, metodo = 'separado', puntaje = NULL,
                          detalle = NULL, decidido_por = %s, fecha = now() WHERE id_registro = %s""",
                (nuevo, usuario, id_registro))
    regs = {r["id_registro"]: r for r in _registros(cur, [id_registro, *otros])}
    for otro in otros:           # que la próxima sincronización no los vuelva a unir
        puntaje, detalle = comparar(regs[id_registro], regs[otro])
        _guardar_par(cur, id_registro, otro, puntaje, detalle, "distinto", usuario, forzar=True)
    return {"clave_cliente": clave, "separado_de": len(otros)}


def separar(id_registro, usuario):
    return _transaccion(lambda cur: _separar(cur, id_registro, usuario))


def _marcar_distintos(cur, id_par, usuario):
    a, b, puntaje, detalle, _ = _par(cur, id_par)
    if _cliente_de(cur, a) == _cliente_de(cur, b):       # ya estaban unidos: se separa b
        return {"separado": b, **_separar(cur, b, usuario)}
    _guardar_par(cur, a, b, puntaje, detalle, "distinto", usuario, forzar=True)
    return {"separado": None}


def marcar_distintos(id_par, usuario):
    return _transaccion(lambda cur: _marcar_distintos(cur, id_par, usuario))


def listar_pares(estado="pendiente", limite=200):
    def correr(cur):
        if not instalado(cur):
            return None
        cur.execute("""SELECT p.id_par, p.estado, p.puntaje, p.detalle, p.decidido_por, p.fecha_decision, p.creado,
                              p.id_registro_a, p.id_registro_b, ma.clave_cliente AS clave_a, mb.clave_cliente AS clave_b
                       FROM public.par_duplicado p
                       LEFT JOIN public.cliente_registro ra ON ra.id_registro = p.id_registro_a
                       LEFT JOIN public.cliente_maestro ma ON ma.id_cliente = ra.id_cliente
                       LEFT JOIN public.cliente_registro rb ON rb.id_registro = p.id_registro_b
                       LEFT JOIN public.cliente_maestro mb ON mb.id_cliente = rb.id_cliente
                       WHERE (%s = 'todos' OR p.estado = %s)
                       ORDER BY p.puntaje DESC, p.id_par LIMIT %s""", (estado, estado, limite))
        cols = [d[0] for d in cur.description]
        pares = [dict(zip(cols, f)) for f in cur.fetchall()]
        ids = sorted({p["id_registro_a"] for p in pares} | {p["id_registro_b"] for p in pares})
        regs = {r["id_registro"]: r for r in _registros(cur, ids)} if ids else {}
        for p in pares:
            p["a"], p["b"] = regs.get(p["id_registro_a"]), regs.get(p["id_registro_b"])
        cur.execute("SELECT estado, COUNT(*) FROM public.par_duplicado GROUP BY estado")
        return {"pares": pares, "conteo": dict(cur.fetchall()), "umbral_auto": AUTO, "umbral_revision": REVISION}
    return _transaccion(correr)


def registros_de(clave):
    """Registros de origen que forman un cliente (vacío si la deduplicación no está instalada)."""
    def correr(cur):
        if not instalado(cur):
            return []
        cur.execute("""SELECT l.id_registro, l.nombre_limpio AS nombre, l.genero, l.edad, l.correo, l.celular,
                              l.ciudad, l.profesion, l.universidad, l.producto_interes, l.medio, l.tipo_base,
                              l.fecha_registro, r.metodo, r.puntaje, r.decidido_por, r.fecha
                       FROM public.cliente_maestro m
                       JOIN public.cliente_registro r USING (id_cliente)
                       JOIN public.clientes_limpios l USING (id_registro)
                       WHERE m.clave_cliente = %s ORDER BY l.id_registro""", (clave,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, f)) for f in cur.fetchall()]
    return _transaccion(correr)


# ================================================================== consola
def _imprimir_reporte(r):
    print(f"Registros: {r['registros']}  ->  clientes únicos: {r['clientes']}  "
          f"(pares comparados: {r['pares_evaluados']}; umbrales: unir ≥ {r['umbral_auto']:g}, "
          f"revisar ≥ {r['umbral_revision']:g})")
    for f in r["fusiones"]:
        motivos = ", ".join(f"{d['motivo']} ({d['aporte']:+d})" for d in f["detalle"])
        print(f"  ✓ Unidos #{f['registros'][0]} {f['nombres'][0]} + #{f['registros'][1]} {f['nombres'][1]}"
              f"  [puntaje {f['puntaje']:g}: {motivos}]")
    for p in r["pendientes"]:
        print(f"  ? Para revisar #{p['registros'][0]} {p['nombres'][0]} / #{p['registros'][1]} {p['nombres'][1]}"
              f"  [puntaje {p['puntaje']:g}]")
    for a in r["avisos"]:
        print(f"  ⚠ {a}")
    for k, n in r["bloques_omitidos"]:
        print(f"  ⚠ Bloque omitido por grande ({n} registros): {k}")
    claves = r.get("claves")
    if claves:
        print("Referencias migradas a la clave estable:")
        for m in claves["movidas"]:
            print(f"  {m['de']} -> {m['a']} ({m['filas']} fila(s) en mensajes / perfiles / hechos)")
        for a in claves["avisos"]:
            print(f"  ⚠ {a}")
        for a in claves["ambiguas"]:
            print(f"  ⚠ Sin migrar (apunta a varios clientes): {a['clave']} -> {a['clientes']}")
        for s in claves["sin_cliente"]:
            print(f"  ⚠ Sin migrar (no corresponde a ningún cliente): {s}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deduplicación de clientes (resolución de entidades)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("migrar", help="instala y deja un perfil por persona")
    m.add_argument("--simular", action="store_true", help="hace todo en una transacción que se revierte")
    m.add_argument("--probar-deshacer", action="store_true", help="con --simular: verifica que deshacer funciona")
    s = sub.add_parser("sincronizar", help="vuelve a buscar duplicados")
    s.add_argument("--simular", action="store_true")
    sub.add_parser("pendientes", help="pares que esperan revisión")
    v = sub.add_parser("ver", help="registros de origen de un cliente")
    v.add_argument("clave")
    u = sub.add_parser("unir", help="une un par (misma persona)")
    u.add_argument("id_par", type=int)
    d = sub.add_parser("distintos", help="marca un par como personas distintas")
    d.add_argument("id_par", type=int)
    se = sub.add_parser("separar", help="saca un registro de su cliente")
    se.add_argument("id_registro", type=int)
    dh = sub.add_parser("deshacer", help="vuelve a las vistas y claves anteriores")
    dh.add_argument("--si", action="store_true", help="confirmación")
    args = ap.parse_args(argv)
    usuario = os.getenv("USERNAME") or os.getenv("USER") or "cli"
    from app import governance

    def auditar(accion, parametros, filas):
        governance.registrar(usuario, "admin", accion, {"origen": "cli", **parametros}, filas)

    if args.cmd == "migrar":
        if args.probar_deshacer and not args.simular:
            raise SystemExit("--probar-deshacer solo se usa junto con --simular.")
        r = migrar(usuario, simular=args.simular, probar_deshacer=args.probar_deshacer)
        _imprimir_reporte(r)
        print(f"clientes_segmentados: {r['clientes_segmentados']} cliente(s).")
        if r.get("prueba_deshacer"):
            print(f"Prueba de deshacer: {r['prueba_deshacer']}")
        print("SIMULACIÓN: no se guardó nada." if args.simular else "Migración aplicada.")
        if not args.simular:
            auditar("dedup_migrar", {"fusiones": len(r["fusiones"]), "pendientes": len(r["pendientes"])},
                    r["clientes"])
    elif args.cmd == "sincronizar":
        r = sincronizar(usuario, simular=args.simular)
        _imprimir_reporte(r)
        print("SIMULACIÓN: no se guardó nada." if args.simular else "Listo.")
        if not args.simular:
            auditar("dedup_sincronizar", {"fusiones": len(r["fusiones"]), "pendientes": len(r["pendientes"])},
                    len(r["fusiones"]))
    elif args.cmd == "pendientes":
        r = listar_pares("pendiente")
        if r is None:
            raise SystemExit("La deduplicación no está instalada.")
        for p in r["pares"]:
            print(f"Par {p['id_par']} (puntaje {p['puntaje']:g}): #{p['id_registro_a']} {p['a']['nombre']} / "
                  f"#{p['id_registro_b']} {p['b']['nombre']}")
        if not r["pares"]:
            print("No hay pares pendientes.")
    elif args.cmd == "ver":
        for f in registros_de(args.clave):
            print(f"#{f['id_registro']} | {f['nombre']} | {f['correo'] or '—'} | {f['celular'] or '—'} | "
                  f"{f['ciudad'] or '—'} | {f['metodo']}")
    elif args.cmd == "unir":
        print(unir_par(args.id_par, usuario))
        auditar("dedup_unir", {"id_par": args.id_par}, 1)
    elif args.cmd == "distintos":
        print(marcar_distintos(args.id_par, usuario))
        auditar("dedup_distintos", {"id_par": args.id_par}, 1)
    elif args.cmd == "separar":
        print(separar(args.id_registro, usuario))
        auditar("dedup_separar", {"id_registro": args.id_registro}, 1)
    elif args.cmd == "deshacer":
        if not args.si:
            raise SystemExit("Esto restaura las vistas anteriores y borra las tablas de deduplicación. "
                             "Confirma con: python -m app.deduplicacion deshacer --si")
        deshacer()
        print("Deduplicación desinstalada: vistas y claves anteriores restauradas.")
        auditar("dedup_deshacer", {}, 0)


if __name__ == "__main__":
    main()
