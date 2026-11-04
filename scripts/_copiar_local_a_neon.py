"""Copia el Postgres local a Neon. No imprime secretos."""
import os
import subprocess
import sys
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))


def get_connection():
    url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if url:
        return psycopg2.connect(url)
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )

PG_BIN = Path(r"C:\Program Files\PostgreSQL\18\bin")
DUMP = Path(os.environ["TEMP"]) / "base_datos_neon.dump"
VERCEL_ENV = Path(os.environ["TEMP"]) / "vercel-neon.env"


def conectar_local():
    local = dotenv_values(Path(".env"))
    os.environ["DB_HOST"] = local.get("DB_HOST") or "localhost"
    os.environ["DB_PORT"] = local.get("DB_PORT") or "5432"
    os.environ["DB_NAME"] = local.get("DB_NAME") or "base_datos"
    os.environ["DB_USER"] = local.get("DB_USER") or "postgres"
    if local.get("DB_PASSWORD"):
        os.environ["DB_PASSWORD"] = local["DB_PASSWORD"]
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("POSTGRES_URL", None)
    return get_connection()


def resumen(conn):
    cur = conn.cursor()
    cur.execute("SELECT extname FROM pg_extension ORDER BY 1")
    print("extensiones", [r[0] for r in cur.fetchall()])
    cur.execute("""
        SELECT n.nspname, c.relkind, c.relname, COALESCE(c.reltuples, 0)::bigint
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'v', 'm')
        ORDER BY c.relkind, c.relname
    """)
    filas = cur.fetchall()
    print("objetos_public", len(filas))
    for esquema, kind, nombre, n in filas:
        tipo = {"r": "tabla", "v": "vista", "m": "matview"}[kind]
        print(f"  {tipo} {nombre} ~{n}")
    cur.close()


def dump_local():
    local = dotenv_values(Path(".env"))
    env = os.environ.copy()
    env["PGPASSWORD"] = local.get("DB_PASSWORD") or ""
    env["PGSSLMODE"] = "prefer"
    cmd = [
        str(PG_BIN / "pg_dump.exe"),
        "-h", local.get("DB_HOST") or "localhost",
        "-p", local.get("DB_PORT") or "5432",
        "-U", local.get("DB_USER") or "postgres",
        "-d", local.get("DB_NAME") or "base_datos",
        "--no-owner",
        "--no-acl",
        "-F", "c",
        "-f", str(DUMP),
    ]
    print("dump_inicio")
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        print("dump_stderr", (r.stderr or "")[-800])
        raise SystemExit(r.returncode)
    print("dump_ok_mb", round(DUMP.stat().st_size / 1024 / 1024, 2))


def url_neon():
    vals = dotenv_values(VERCEL_ENV)
    url = vals.get("DATABASE_URL_UNPOOLED") or vals.get("POSTGRES_URL_NON_POOLING") or vals.get("DATABASE_URL")
    if not url:
        raise SystemExit("no DATABASE_URL en env de Vercel")
    return url


def restore_neon():
    url = url_neon()
    env = os.environ.copy()
    env.pop("PGPASSWORD", None)
    cmd = [
        str(PG_BIN / "pg_restore.exe"),
        "--no-owner",
        "--no-acl",
        "--clean",
        "--if-exists",
        "-d", url,
        str(DUMP),
    ]
    print("restore_inicio")
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    err = (r.stderr or "")
    # pg_restore often exits 1 on benign warnings (extensions already exist, etc.)
    lineas = [ln for ln in err.splitlines() if ln.strip() and "warning:" not in ln.lower()]
    print("restore_code", r.returncode)
    print("restore_avisos", len(err.splitlines()), "errores_no_warning", len(lineas))
    for ln in lineas[:30]:
        # redact connection strings if any leaked
        if "postgresql://" in ln.lower() or "password" in ln.lower():
            print("  [redactado]")
        else:
            print(" ", ln[:240])
    if r.returncode not in (0, 1):
        raise SystemExit(r.returncode)


def verificar_neon():
    os.environ["DATABASE_URL"] = url_neon()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1")
    print("neon_ping", cur.fetchone()[0])
    for tabla in ("clientes", "clientes_limpios", "clientes_segmentados", "conocimiento"):
        try:
            cur.execute(f"SELECT COUNT(*) FROM public.{tabla}")
            print("neon", tabla, cur.fetchone()[0])
        except Exception as e:
            conn.rollback()
            print("neon", tabla, "error", str(e).splitlines()[0][:160])
    cur.close()
    conn.close()


def main():
    os.chdir(Path(__file__).resolve().parents[1])
    conn = conectar_local()
    try:
        resumen(conn)
    finally:
        conn.close()
    dump_local()
    restore_neon()
    verificar_neon()


if __name__ == "__main__":
    sys.exit(main())
