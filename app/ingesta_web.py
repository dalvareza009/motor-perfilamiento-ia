"""Ingesta del catálogo de productos desde globalseguroscolombia.com con Firecrawl.

El contexto de vida de las personas (trabajo, estudios, familia) no sale de este sitio:
se lee de perfiles públicos autorizados con  python -m app.ingesta_perfiles

Flujo: scrape -> fragmentos en `conocimiento` con activo = FALSE -> revisión humana -> aprobar.
Solo lo aprobado llega al asistente (y se vectoriza al aprobar).

  python -m app.ingesta_web sitio --solo educativo            páginas del seguro educativo (barato: ~1 crédito/página)
  python -m app.ingesta_web sitio                              todas las páginas de producto + portafolio
  python -m app.ingesta_web sitio --solo educativo --pdf       además clausulados (+1 crédito POR PÁGINA de PDF)
  python -m app.ingesta_web scrape "Seguro educativo" URL...   páginas sueltas (producto "auto" = según el título)
  python -m app.ingesta_web resumen | pendientes | ver ID | aprobar ... | desactivar ID...

.env:  SITIO_DOMINIO=globalseguroscolombia.com     FIRECRAWL_API_KEY=fc-... (opcional)
"""
import argparse
import hashlib
import os
from urllib.parse import urlparse

from app import governance, web_texto
from app.database import get_connection

BASE = "https://www.globalseguroscolombia.com"
URL_PORTAFOLIO = f"{BASE}/productos/"
# clave -> (nombre del producto tal como lo usa la base de clientes, ruta). Fuente: menú "Soluciones" del sitio.
CATALOGO = {
    "educativo": ("Seguro educativo", "/seguros-educativos/"),
    "vida": ("Seguro de vida", "/seguros-de-vida/"),
    "renta-vitalicia": ("Seguro renta vitalicia", "/seguro-renta-vitalicia/"),
    "renta-voluntaria": ("Seguro renta voluntaria", "/seguro-renta-voluntaria/"),
    "previsional": ("Seguro previsional", "/seguro-previsional/"),
    "pension": ("Seguro de pensión", "/seguro-de-pension/"),
    "accidentes": ("Seguro de accidentes personales", "/seguro-de-accidentes-personales/"),
}


def _usuario(args=None):
    """Quien queda en la auditoría: el usuario de la web si viene en args; si no, el del sistema."""
    return getattr(args, "usuario", None) or os.getenv("USERNAME") or os.getenv("USER") or "cli"


def _dominio_permitido(url):
    dominio = (os.getenv("SITIO_DOMINIO") or "").lower().strip()
    host = (urlparse(url).hostname or "").lower()
    return bool(dominio) and (host == dominio or host.endswith("." + dominio))


def _markdown(doc):
    if isinstance(doc, dict):
        return doc.get("markdown") or ""
    return getattr(doc, "markdown", None) or ""


def _scrape(fc, url):
    if not _dominio_permitido(url):
        print(f"✗ Omitida (fuera de {os.getenv('SITIO_DOMINIO')}): {url}")
        return None
    try:
        return _markdown(fc.scrape(url, formats=["markdown"]))
    except Exception as e:                      # cuota, red, página no disponible...
        print(f"✗ Falló {url}: {e}")
        return None


def _guardar(producto, url, fragmentos):
    nuevos = actualizados = sin_cambios = 0
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for f in fragmentos:
                titulo, cuerpo = f["titulo"], f["contenido"]
                h = hashlib.sha256(cuerpo.encode("utf-8")).hexdigest()
                cur.execute("""SELECT id_conocimiento, hash_contenido FROM public.conocimiento
                               WHERE LOWER(producto) = LOWER(%s) AND fuente_url = %s AND titulo = %s""",
                            (producto, url, titulo))
                fila = cur.fetchone()
                if fila and fila[1] == h:
                    sin_cambios += 1
                elif fila:    # cambió en el sitio: vuelve a revisión
                    cur.execute("""UPDATE public.conocimiento SET contenido = %s, hash_contenido = %s,
                                   categoria = %s, activo = FALSE, fecha_actualizacion = now()
                                   WHERE id_conocimiento = %s""", (cuerpo, h, f["categoria"], fila[0]))
                    actualizados += 1
                else:
                    cur.execute("""INSERT INTO public.conocimiento
                                   (categoria, producto, titulo, contenido, activo, fecha_actualizacion,
                                    fuente_url, hash_contenido)
                                   VALUES (%s,%s,%s,%s,FALSE,now(),%s,%s)""",
                                (f["categoria"], producto, titulo, cuerpo, url, h))
                    nuevos += 1
        conn.commit()
    finally:
        conn.close()
    return nuevos, actualizados, sin_cambios


def _procesar_pagina(fc, url, producto, pdfs, args):
    md = _scrape(fc, url)
    if md is None:
        return
    frags, omitidos = web_texto.fragmentos_pagina(md)
    if not frags:
        print(f"⚠ {url}: no se encontró contenido útil.")
        return
    if producto == "auto":      # portafolio: el producto sale del título de cada sección
        por_producto = {}
        for f in frags:
            fam = web_texto.familia_por_grupo(f["grupo"])
            if fam:
                por_producto.setdefault(fam, []).append(f)
    else:
        por_producto = {producto: frags}
        for u in web_texto.enlaces_pdf(md, getattr(args, "con_tarifas", False)):
            pdfs.setdefault(u, producto)
    for prod, fr in por_producto.items():
        n, a, s = _guardar(prod, url, fr)
        print(f"✓ {url} → {prod}: {n} nuevos, {a} actualizados, {s} sin cambios.")
    if omitidos:
        print(f"   ({omitidos} secciones genéricas omitidas: su contenido está dentro de cada producto)")


def _procesar_pdfs(fc, pdfs, args):
    if not pdfs:
        return
    filtro = (args.pdf_solo or "").lower()
    candidatos = [(u, p) for u, p in pdfs.items() if filtro in web_texto._n(u) or filtro in u.lower()]
    print(f"\nPDFs encontrados: {len(pdfs)} (tras filtro: {len(candidatos)})")
    for u, p in candidatos:
        print(f"  - [{p}] {web_texto.nombre_pdf(u)}")
    if not args.pdf:
        print("No se descargaron. Para incluirlos: --pdf [--pdf-solo TEXTO] [--max-pdfs N]  "
              "(+1 crédito de Firecrawl por página de PDF).")
        return
    for u, producto in candidatos[:args.max_pdfs]:
        md = _scrape(fc, u)
        if not md:
            print(f"⚠ {u}: PDF vacío o ilegible (¿escaneado?).")
            continue
        frags, truncado = web_texto.fragmentos_pdf(md, web_texto.nombre_pdf(u), args.max_fragmentos)
        n, a, s = _guardar(producto, u, frags)
        print(f"✓ PDF {web_texto.nombre_pdf(u)} → {producto}: {n} nuevos, {a} actualizados, {s} sin cambios."
              + ("  ⚠ truncado al tope de fragmentos." if truncado else ""))
    if len(candidatos) > args.max_pdfs:
        print(f"⚠ Quedaron {len(candidatos) - args.max_pdfs} PDFs sin procesar (--max-pdfs {args.max_pdfs}).")


def _cliente():
    if not os.getenv("SITIO_DOMINIO"):
        raise SystemExit("Define SITIO_DOMINIO en el .env (por ejemplo, globalseguroscolombia.com).")
    from firecrawl import Firecrawl      # import tardío: el resto del módulo no lo necesita
    return Firecrawl()                   # lee FIRECRAWL_API_KEY del entorno si existe


def cmd_scrape(args):
    fc, pdfs = _cliente(), {}
    for url in args.urls:
        _procesar_pagina(fc, url, args.producto, pdfs, args)
    _procesar_pdfs(fc, pdfs, args)
    print("\nRevisa con:  python -m app.ingesta_web resumen")


def cmd_sitio(args):
    fc, pdfs = _cliente(), {}
    for clave in (args.solo or CATALOGO):
        producto, ruta = CATALOGO[clave]
        _procesar_pagina(fc, BASE + ruta, producto, pdfs, args)
    if not args.sin_portafolio:
        _procesar_pagina(fc, URL_PORTAFOLIO, "auto", pdfs, args)
    _procesar_pdfs(fc, pdfs, args)
    print("\nRevisa con:  python -m app.ingesta_web resumen")


def _filtros_sql(producto, categoria):
    where, params = ["activo = FALSE", "fuente_url IS NOT NULL"], []
    if producto:
        where.append("LOWER(producto) = LOWER(%s)")
        params.append(producto)
    if categoria:
        where.append("LOWER(categoria) = LOWER(%s)")
        params.append(categoria)
    return " AND ".join(where), params


def cmd_resumen(_):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT producto, categoria, COUNT(*) FILTER (WHERE NOT activo),
                                  COUNT(*) FILTER (WHERE activo)
                           FROM public.conocimiento WHERE fuente_url IS NOT NULL
                           GROUP BY 1, 2 ORDER BY 1, 2""")
            filas = cur.fetchall()
    finally:
        conn.close()
    if not filas:
        print("Aún no hay conocimiento extraído del sitio.")
        return
    print(f"{'Producto':36} {'Categoría':20} {'Pendientes':>10} {'Activos':>8}")
    for p, c, pend, act in filas:
        print(f"{p:36} {c:20} {pend:>10} {act:>8}")


def cmd_pendientes(args):
    where, params = _filtros_sql(args.producto, args.categoria)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"""SELECT id_conocimiento, producto, categoria, titulo, LEFT(contenido, 90)
                            FROM public.conocimiento WHERE {where} ORDER BY id_conocimiento LIMIT %s""",
                        params + [args.limite])
            filas = cur.fetchall()
    finally:
        conn.close()
    if not filas:
        print("No hay fragmentos pendientes.")
    for f in filas:
        print(f"#{f[0]} | {f[1]} | {f[2]} | {f[3]}\n     {f[4].replace(chr(10), ' ')}...")
    if len(filas) == args.limite:
        print(f"(mostrando {args.limite}; usa --limite, --producto o --categoria)")


def cmd_ver(args):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id_conocimiento, producto, categoria, titulo, contenido, activo, fuente_url
                           FROM public.conocimiento WHERE id_conocimiento = %s""", (args.id,))
            f = cur.fetchone()
    finally:
        conn.close()
    if not f:
        raise SystemExit("No existe.")
    print(f"#{f[0]} | {f[1]} | {f[2]} | activo={f[5]}\n{f[3]}\nFuente: {f[6]}\n\n{f[4]}")


def cmd_aprobar(args):
    if not args.ids and not args.todos:
        raise SystemExit("Indica ids, o usa --todos [--producto P] [--categoria C].")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if args.todos:
                where, params = _filtros_sql(args.producto, args.categoria)
                cur.execute(f"UPDATE public.conocimiento SET activo = TRUE, fecha_actualizacion = now() "
                            f"WHERE {where}", params)
            else:
                cur.execute("""UPDATE public.conocimiento SET activo = TRUE, fecha_actualizacion = now()
                               WHERE id_conocimiento = ANY(%s) AND fuente_url IS NOT NULL""", (args.ids,))
            n = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    governance.registrar(_usuario(args), "admin", "aprobar_conocimiento",
                         {"ids": args.ids, "todos": args.todos, "producto": args.producto,
                          "categoria": args.categoria}, n)
    print(f"{n} fragmento(s) aprobado(s): ya los usa el asistente.")
    try:
        from app import vectorizar
        r = vectorizar.sincronizar()
        print(f"Índice vectorial actualizado ({r['vectorizados']} fragmentos vectorizados).")
    except Exception as e:
        print(f"⚠ Aprobado, pero no se pudo vectorizar ({e}). Ejecuta: python -m app.vectorizar")


def cmd_desactivar(args):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE public.conocimiento SET activo = FALSE, fecha_actualizacion = now()
                           WHERE id_conocimiento = ANY(%s) AND fuente_url IS NOT NULL""", (args.ids,))
            n = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    governance.registrar(_usuario(args), "admin", "desactivar_conocimiento", {"ids": args.ids}, n)
    print(f"{n} fragmento(s) desactivado(s).")
    try:
        from app import vectorizar
        vectorizar.sincronizar()
    except Exception as e:
        print(f"⚠ No se pudo actualizar el índice vectorial ({e}). Ejecuta: python -m app.vectorizar")


def _opciones_pdf(p):
    p.add_argument("--pdf", action="store_true", help="descargar también los PDFs (cuesta créditos por página)")
    p.add_argument("--pdf-solo", default="", help="solo PDFs cuyo nombre contenga este texto")
    p.add_argument("--max-pdfs", type=int, default=5)
    p.add_argument("--max-fragmentos", type=int, default=120, help="tope de fragmentos por PDF")
    p.add_argument("--con-tarifas", action="store_true", help="incluir PDFs de tarifas (por defecto se omiten)")


def main():
    ap = argparse.ArgumentParser(description="Ingesta de conocimiento desde el sitio propio (Firecrawl)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sitio", help="recorre las páginas de producto del sitio")
    s.add_argument("--solo", nargs="+", choices=list(CATALOGO), help="limitar a ciertos productos")
    s.add_argument("--sin-portafolio", action="store_true", help="omitir la página /productos/")
    _opciones_pdf(s)
    s.set_defaults(fn=cmd_sitio)

    s = sub.add_parser("scrape", help="páginas sueltas")
    s.add_argument("producto", help='nombre del producto, o "auto" para deducirlo del título')
    s.add_argument("urls", nargs="+")
    _opciones_pdf(s)
    s.set_defaults(fn=cmd_scrape)

    sub.add_parser("resumen").set_defaults(fn=cmd_resumen)
    p = sub.add_parser("pendientes")
    p.add_argument("--producto"); p.add_argument("--categoria"); p.add_argument("--limite", type=int, default=40)
    p.set_defaults(fn=cmd_pendientes)
    v = sub.add_parser("ver"); v.add_argument("id", type=int); v.set_defaults(fn=cmd_ver)
    a = sub.add_parser("aprobar"); a.add_argument("ids", nargs="*", type=int)
    a.add_argument("--todos", action="store_true"); a.add_argument("--producto"); a.add_argument("--categoria")
    a.set_defaults(fn=cmd_aprobar)
    d = sub.add_parser("desactivar"); d.add_argument("ids", nargs="+", type=int); d.set_defaults(fn=cmd_desactivar)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()