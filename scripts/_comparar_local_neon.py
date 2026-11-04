"""Compara objeto a objeto el Postgres local vs Neon. No imprime secretos ni filas."""
import os
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parents[1]
VERCEL_ENV = Path(os.environ["TEMP"]) / "vercel-neon.env"


def local_conn():
    v = dotenv_values(RAIZ / ".env")
    return psycopg2.connect(
        host=v.get("DB_HOST") or "localhost",
        port=v.get("DB_PORT") or "5432",
        dbname=v.get("DB_NAME") or "base_datos",
        user=v.get("DB_USER") or "postgres",
        password=v.get("DB_PASSWORD") or "",
    )


def neon_conn():
    vals = dotenv_values(VERCEL_ENV)
    url = vals.get("DATABASE_URL_UNPOOLED") or vals.get("POSTGRES_URL_NON_POOLING") or vals.get("DATABASE_URL")
    if not url:
        raise SystemExit("falta env de Vercel")
    return psycopg2.connect(url)


def catalogo(conn):
    cur = conn.cursor()
    cur.execute("SELECT extname FROM pg_extension ORDER BY 1")
    exts = [r[0] for r in cur.fetchall()]
    cur.execute("""
        SELECT c.relkind, c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r','v','m','S')
        ORDER BY 1, 2
    """)
    objetos = cur.fetchall()
    cur.execute("""
        SELECT p.proname
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
        ORDER BY 1
    """)
    funcs = [r[0] for r in cur.fetchall()]
    conteos = {}
    for kind, nombre in objetos:
        if kind in ("r", "v", "m"):
            try:
                cur.execute(f'SELECT COUNT(*) FROM public."{nombre}"')
                conteos[nombre] = cur.fetchone()[0]
            except Exception as e:
                conn.rollback()
                conteos[nombre] = f"error:{type(e).__name__}"
    cur.close()
    return exts, objetos, funcs, conteos


def main():
    os.chdir(RAIZ)
    a, b = local_conn(), neon_conn()
    try:
        ae, ao, af, ac = catalogo(a)
        be, bo, bf, bc = catalogo(b)
    finally:
        a.close()
        b.close()

    print("ext_local", ae)
    print("ext_neon", be)
    print("ext_faltan_en_neon", sorted(set(ae) - set(be)))
    print("funcs_local", af)
    print("funcs_neon", bf)
    print("funcs_faltan_en_neon", sorted(set(af) - set(bf)))

    lo = {(k, n) for k, n in ao}
    ne = {(k, n) for k, n in bo}
    print("objetos_solo_local", sorted(lo - ne))
    print("objetos_solo_neon", sorted(ne - lo))

    nombres = sorted(set(ac) | set(bc))
    print("conteos")
    diffs = 0
    for n in nombres:
        va, vb = ac.get(n, "ausente"), bc.get(n, "ausente")
        marca = "OK" if va == vb else "DIFF"
        if marca == "DIFF":
            diffs += 1
        print(f"  {marca} {n}: local={va} neon={vb}")
    print("diferencias", diffs)


if __name__ == "__main__":
    main()
