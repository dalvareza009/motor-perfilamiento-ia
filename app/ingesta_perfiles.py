"""Ingesta de perfiles públicos autorizados (LinkedIn, Instagram, Facebook, X, TikTok).

LinkedIn e Instagram no se abren como página: Firecrawl los bloquea. Esos dos se consultan
como ficha (cargo, empresa, estudios, ciudad, bio) y el resto sigue por la página pública.
Lee data/perfiles_autorizados.json y guarda hechos con activo = FALSE hasta la revisión.

  python -m app.ingesta_perfiles
  python -m app.ingesta_perfiles resumen | pendientes | ver ID | aprobar ID... | aprobar --todos | descartar ID...

El catálogo de productos sigue en:  python -m app.ingesta_web sitio
Las publicaciones públicas de LinkedIn están en:  python -m app.ingesta_linkedin
"""
import argparse
import hashlib
import json
import os
import threading
from pathlib import Path

from app import governance, perfil_redes
from app.database import get_connection

ARCHIVO = Path(__file__).resolve().parents[1] / "data" / "perfiles_autorizados.json"
CATEGORIAS_DE_VIDA = ("Trabajo", "Estudios", "Ubicacion", "Familia", "Situacion actual", "Edad", "Interes")
AUTORIZACION_LOTE = "Perfil leído en el motor: se asume autorización previa."
_ARCHIVO_LOCK = threading.Lock()

DDL = """
CREATE TABLE IF NOT EXISTS public.hechos_perfil (
    id_hecho SERIAL PRIMARY KEY,
    clave_cliente TEXT,
    nombre TEXT NOT NULL,
    red TEXT NOT NULL,
    fuente_url TEXT NOT NULL,
    categoria TEXT NOT NULL,
    titulo TEXT NOT NULL,
    contenido TEXT NOT NULL,
    hash_contenido TEXT NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS hechos_perfil_fuente_titulo
    ON public.hechos_perfil (fuente_url, titulo);
ALTER TABLE public.hechos_perfil ADD COLUMN IF NOT EXISTS descartado BOOLEAN NOT NULL DEFAULT FALSE;
"""


def _usuario(args=None):
    """Quien queda en la auditoría: el usuario de la web si viene en args; si no, el del sistema."""
    return getattr(args, "usuario", None) or os.getenv("USERNAME") or os.getenv("USER") or "cli"


def asegurar_tabla():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for sentencia in DDL.split(";"):
                if sentencia.strip():
                    cur.execute(sentencia)
        conn.commit()
    finally:
        conn.close()


def _markdown(doc):
    if isinstance(doc, dict):
        return doc.get("markdown") or ""
    return getattr(doc, "markdown", None) or ""


def _aviso_firecrawl(texto):
    if "must accept" in texto.lower() or "terms" in texto.lower() and "apollo" in texto.lower():
        return ("Falta que un administrador acepte los términos de Apollo en "
                "https://www.firecrawl.dev/app/alexandria/apollo")
    if "Enrichment is not enabled" in texto or "not enabled for person" in texto:
        return ("La cuenta de Firecrawl no tiene activa la consulta de perfiles de personas. "
                "Un administrador la habilita en https://www.firecrawl.dev/app/alexandria?enrichment=true")
    if "do not support this site" in texto or "Website Not Supported" in texto:
        return "Firecrawl no abre esa página de perfil. " + texto
    return texto


def _aviso_vacio(red, ya_apollo=False):
    if red == "linkedin" and ya_apollo:
        return "ni el índice ni el enriquecimiento masivo tienen esa URL de LinkedIn."
    if red == "linkedin":
        return ("el índice no tiene esa URL de LinkedIn. Hay otra fuente que resuelve slugs antiguos, "
                "pero un administrador tiene que aceptar sus términos en "
                "https://www.firecrawl.dev/app/alexandria/apollo")
    if red == "instagram":
        return "el índice no tiene ese perfil de Instagram, y Firecrawl no abre la página de Instagram."
    return "el índice no tiene esa URL."


def _unir_contactos(*listas):
    vistos, salida = set(), []
    for contacto in listas:
        for c in contacto or []:
            clave = (c["titulo"], c["contenido"])
            if clave not in vistos:
                vistos.add(clave)
                salida.append(c)
    return salida


def _texto_de_alexandria(respuesta, red, ya_apollo=False):
    """-> (markdown, contactos, aviso)."""
    items = getattr(respuesta, "alexandria", None) or []
    if not items:
        return "", [], [], "Firecrawl no devolvió ficha."
    item = items[0]
    error = getattr(item, "error", None)
    if error:
        mensaje = getattr(error, "message", None) or str(error)
        return "", [], [], _aviso_firecrawl(mensaje)
    data = getattr(item, "data", None)
    if perfil_redes.es_perfil_privado(data):
        return "", [], [], "el perfil está marcado como privado."
    if perfil_redes.ficha_vacia(data):
        return "", [], [], _aviso_vacio(red, ya_apollo)
    texto = perfil_redes.markdown_desde_ficha(data)
    contactos = perfil_redes.contactos_de_ficha(data)
    hechos = perfil_redes.hechos_desde_ficha(data)
    if not texto and not contactos and not hechos:
        return "", [], [], "la ficha no trae trabajo, estudios, ciudad, bio ni contacto."
    return texto, contactos, hechos, None


def _leer_perfil(fc, red, url):
    """-> (markdown, contactos, hechos, aviso). LinkedIn e Instagram van por ficha; el resto, por la página."""
    try:
        if red == "linkedin":
            respuesta = fc.scrape(alexandria={
                "provider": "fullenrich",
                "capability": "people/match",
                "options": {"linkedin_url": url},
            })
            texto, contactos, hechos, aviso = _texto_de_alexandria(respuesta, red)
            if texto or contactos or hechos or (aviso and "términos de Apollo" not in aviso and "índice no tiene" not in aviso):
                return texto, _unir_contactos(contactos, perfil_redes.contactos_de_texto(texto)), hechos, aviso
            respuesta = fc.scrape(alexandria={
                "provider": "apollo",
                "capability": "people/bulk-match",
                "options": {"details": [{"linkedin_url": url}]},
            })
            texto, contactos, hechos, aviso = _texto_de_alexandria(respuesta, red, ya_apollo=True)
            return texto, _unir_contactos(contactos, perfil_redes.contactos_de_texto(texto)), hechos, aviso
        if red == "instagram":
            respuesta = fc.scrape(alexandria={
                "provider": "oriane",
                "capability": "instagram/profile-lookup",
                "options": {"url": url, "projection": "default"},
            })
            texto, contactos, hechos, aviso = _texto_de_alexandria(respuesta, red)
            return texto, _unir_contactos(contactos, perfil_redes.contactos_de_texto(texto)), hechos, aviso
        texto = _markdown(fc.scrape(url, formats=["markdown"]))
        return texto, perfil_redes.contactos_de_texto(texto), [], None
    except Exception as e:
        return "", [], [], _aviso_firecrawl(str(e))


def _guardar(persona, red, url, fragmentos):
    nuevos = actualizados = sin_cambios = 0
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for f in fragmentos:
                cuerpo = f["contenido"]
                h = hashlib.sha256(cuerpo.encode("utf-8")).hexdigest()
                cur.execute("""SELECT id_hecho, hash_contenido FROM public.hechos_perfil
                               WHERE fuente_url = %s AND titulo = %s""", (url, f["titulo"]))
                fila = cur.fetchone()
                if fila and fila[1] == h:
                    sin_cambios += 1
                elif fila:
                    cur.execute("""UPDATE public.hechos_perfil
                                   SET contenido = %s, hash_contenido = %s, categoria = %s,
                                       clave_cliente = COALESCE(%s, clave_cliente), nombre = %s, red = %s,
                                       activo = FALSE, descartado = FALSE, fecha_actualizacion = now()
                                   WHERE id_hecho = %s""",
                                (cuerpo, h, f["categoria"], persona["clave_cliente"],
                                 persona["nombre"], red, fila[0]))
                    actualizados += 1
                else:
                    cur.execute("""INSERT INTO public.hechos_perfil
                                   (clave_cliente, nombre, red, fuente_url, categoria, titulo,
                                    contenido, hash_contenido, activo, fecha_actualizacion)
                                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,FALSE,now())""",
                                (persona["clave_cliente"], persona["nombre"], red, url,
                                 f["categoria"], f["titulo"], cuerpo, h))
                    nuevos += 1
        conn.commit()
    finally:
        conn.close()
    return nuevos, actualizados, sin_cambios


def _depurar_sobrantes(url, fragmentos):
    """Quita de esa URL los hechos viejos que esta lectura ya no trae, como un id interno."""
    titulos = [f["titulo"] for f in fragmentos]
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""DELETE FROM public.hechos_perfil
                           WHERE fuente_url = %s AND NOT (titulo = ANY(%s))""", (url, titulos))
        conn.commit()
    finally:
        conn.close()


def _cargar_lista():
    if not ARCHIVO.is_file():
        return []
    try:
        data = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _guardar_lista(data):
    ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
    temporal = ARCHIVO.with_suffix(".json.tmp")
    temporal.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporal, ARCHIVO)


def registrar_perfil_leido(nombre, red, url, clave_cliente=None):
    """Guarda a la persona con el nombre que salió de la red. Une por URL o por nombre."""
    clasificada = perfil_redes.clasificar_url(url)
    if not clasificada:
        return None
    red, limpia = clasificada
    nombre = str(nombre or "").strip()
    clave = str(clave_cliente or "").strip()

    def misma_url(u):
        c = perfil_redes.clasificar_url(str(u))
        return bool(c) and c[1].rstrip("/") == limpia.rstrip("/")

    with _ARCHIVO_LOCK:
        data = _cargar_lista()
        hallada = None
        for item in data:
            if not isinstance(item, dict):
                continue
            if any(misma_url(u) for u in (item.get("urls") or [])):
                hallada = item
                break
        if hallada is None and nombre and len(nombre) >= 3:
            clave_n = perfil_redes._n(nombre)
            for item in data:
                if isinstance(item, dict) and perfil_redes._n(item.get("nombre") or "") == clave_n:
                    hallada = item
                    break
        if hallada is None:
            hallada = {
                "nombre": nombre or limpia,
                "clave_cliente": clave,
                "autorizado": True,
                "autorizacion": AUTORIZACION_LOTE,
                "urls": [limpia],
            }
            data.append(hallada)
        else:
            actual = str(hallada.get("nombre") or "").strip()
            if nombre and len(nombre) >= 3 and (len(nombre) > len(actual) or not actual or actual.startswith("http")):
                hallada["nombre"] = nombre
            hallada["autorizado"] = True
            if len(str(hallada.get("autorizacion") or "").strip()) < 15:
                hallada["autorizacion"] = AUTORIZACION_LOTE
            urls = [str(u) for u in (hallada.get("urls") or [])]
            if not any(misma_url(u) for u in urls):
                urls.append(limpia)
            hallada["urls"] = urls
            if clave and not str(hallada.get("clave_cliente") or "").strip():
                hallada["clave_cliente"] = clave
        _guardar_lista(data)
    return hallada


def objetivos_desde_urls(urls, data=None):
    """Una entrada por URL válida. Si ya estaba en el archivo, reutiliza esa persona."""
    if data is None:
        data = _cargar_lista()
    personas, _ = perfil_redes.cargar_autorizados(data)
    por_url = {}
    for persona in personas:
        for entrada in persona.get("urls") or []:
            por_url[entrada["url"].rstrip("/")] = (persona, entrada)
    objetivos, vistos, avisos = [], set(), []
    for cruda in urls or []:
        clasificada = perfil_redes.clasificar_url((cruda or "").strip())
        if not clasificada:
            avisos.append(f"URL no reconocida: {cruda}")
            continue
        red, limpia = clasificada
        clave = limpia.rstrip("/")
        if clave in vistos:
            continue
        vistos.add(clave)
        if clave in por_url:
            objetivos.append(por_url[clave])
            continue
        persona = {
            "nombre": "",
            "clave_cliente": None,
            "autorizacion": AUTORIZACION_LOTE,
            "urls": [{"red": red, "url": limpia}],
        }
        objetivos.append((persona, {"red": red, "url": limpia}))
    return objetivos, avisos


def objetivos_de_pedido(nombres=None, urls=None, todos=False, data=None):
    """Solo lo pedido: URLs pegadas, nombres concretos, o el archivo completo si todos=True.

    Un lote de URLs nunca se expande a las personas autorizadas anteriores.
    """
    if data is None:
        data = _cargar_lista()
    urls_limpias = [str(u).strip() for u in (urls or []) if u and str(u).strip()]
    if urls_limpias:
        return objetivos_desde_urls(urls_limpias, data)
    nombres_limpios = [str(n).strip() for n in (nombres or []) if n and str(n).strip()]
    if nombres_limpios:
        pedidas = set(nombres_limpios)
        data = [p for p in data if isinstance(p, dict) and str(p.get("nombre") or "").strip() in pedidas]
        personas, avisos = perfil_redes.cargar_autorizados(data)
        return [(p, u) for p in personas for u in p["urls"]], avisos
    if todos:
        personas, avisos = perfil_redes.cargar_autorizados(data)
        return [(p, u) for p in personas for u in p["urls"]], avisos
    return [], ["Pega URLs de LinkedIn, Facebook, Instagram o X, una por línea."]


def _leer(path):
    archivo = Path(path)
    if not archivo.is_file():
        raise SystemExit(
            "No está data/perfiles_autorizados.json.\n"
            "Copia data/perfiles_autorizados.ejemplo.json, pon tu perfil y el de quienes "
            "autorizaron, con autorizado en true y la URL pública de cada red."
        )
    with archivo.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise SystemExit("El archivo debe ser una lista de personas.")
    return data


def cmd_perfiles(args):
    personas, avisos = perfil_redes.cargar_autorizados(_leer(args.archivo))
    for aviso in avisos:
        print(f"⚠ {aviso}")
    if not personas:
        raise SystemExit("No hay personas autorizadas con un perfil público utilizable.")
    asegurar_tabla()
    from firecrawl import Firecrawl
    fc = Firecrawl()
    for persona in personas:
        print(f"\n{persona['nombre']}")
        for perfil in persona["urls"]:
            url = perfil["url"]
            md, contactos, hechos_ficha, aviso = _leer_perfil(fc, perfil["red"], url)
            if aviso:
                print(f"✗ Falló {url}: {aviso}")
                continue
            if perfil_redes.es_muro_de_acceso(md) or not (md.strip() or contactos or hechos_ficha):
                print(f"⚠ {url}: el perfil no está visible sin iniciar sesión.")
                continue
            hechos = hechos_ficha or (perfil_redes.hechos_de_perfil(md) if md.strip() else [])
            if not hechos and not contactos:
                print(f"⚠ {url}: no apareció trabajo, estudios, ubicación, familia ni contacto.")
                continue
            sugeridos = perfil_redes.sugerir_productos(hechos) if hechos else []
            fragmentos = hechos + contactos + sugeridos
            n, a, s = _guardar(persona, perfil["red"], url, fragmentos)
            _depurar_sobrantes(url, fragmentos)
            print(f"✓ {perfil['red']} {url}: {n} nuevos, {a} actualizados, {s} sin cambios.")
            for sug in sugeridos:
                print(f"   Sugerido (pendiente de revisión): {sug['titulo']}")
                print(f"     {sug['contenido']}")
    print("\nRevisa con:  python -m app.ingesta_perfiles pendientes")
    print("Aprueba con: python -m app.ingesta_perfiles aprobar ID...")


def cmd_resumen(_):
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT nombre, categoria,
                                  COUNT(*) FILTER (WHERE NOT activo AND NOT descartado),
                                  COUNT(*) FILTER (WHERE activo)
                           FROM public.hechos_perfil
                           GROUP BY 1, 2 ORDER BY 1, 2""")
            filas = cur.fetchall()
    finally:
        conn.close()
    if not filas:
        print("Aún no hay hechos de perfiles.")
        return
    print(f"{'Persona':28} {'Categoría':22} {'Pendientes':>10} {'Activos':>8}")
    for nombre, categoria, pend, act in filas:
        print(f"{nombre:28} {categoria:22} {pend:>10} {act:>8}")


def cmd_pendientes(args):
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id_hecho, nombre, red, categoria, titulo, LEFT(contenido, 110)
                           FROM public.hechos_perfil
                           WHERE activo = FALSE AND descartado = FALSE
                             AND (%s = '' OR LOWER(nombre) = LOWER(%s))
                           ORDER BY id_hecho LIMIT %s""",
                        (args.nombre or "", args.nombre or "", args.limite))
            filas = cur.fetchall()
    finally:
        conn.close()
    if not filas:
        print("No hay hechos pendientes.")
    for f in filas:
        print(f"#{f[0]} | {f[1]} | {f[2]} | {f[3]} | {f[4]}\n     {f[5].replace(chr(10), ' ')}")


def cmd_ver(args):
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id_hecho, nombre, clave_cliente, red, categoria, titulo,
                                  contenido, activo, fuente_url
                           FROM public.hechos_perfil WHERE id_hecho = %s""", (args.id,))
            f = cur.fetchone()
    finally:
        conn.close()
    if not f:
        raise SystemExit("No existe.")
    print(f"#{f[0]} | {f[1]} | clave={f[2] or '—'} | {f[3]} | {f[4]} | activo={f[7]}\n"
          f"{f[5]}\nFuente: {f[8]}\n\n{f[6]}")


def cmd_aprobar(args):
    if not args.ids and not args.todos:
        raise SystemExit("Indica ids, o usa --todos.")
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if args.todos:
                grupo = getattr(args, "grupo", "") or ""
                from app.redes_seguidas import CATEGORIAS_RED
                if grupo == "red":
                    cur.execute("""UPDATE public.hechos_perfil SET activo = TRUE, fecha_actualizacion = now()
                                   WHERE activo = FALSE AND descartado = FALSE
                                     AND categoria = ANY(%s)""", (list(CATEGORIAS_RED),))
                elif grupo == "ficha":
                    cur.execute("""UPDATE public.hechos_perfil SET activo = TRUE, fecha_actualizacion = now()
                                   WHERE activo = FALSE AND descartado = FALSE
                                     AND NOT (categoria = ANY(%s))""", (list(CATEGORIAS_RED),))
                else:
                    cur.execute("""UPDATE public.hechos_perfil SET activo = TRUE, fecha_actualizacion = now()
                                   WHERE activo = FALSE AND descartado = FALSE""")
            else:
                cur.execute("""UPDATE public.hechos_perfil SET activo = TRUE, fecha_actualizacion = now()
                               WHERE id_hecho = ANY(%s)""", (args.ids,))
            n = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    governance.registrar(_usuario(args), "admin", "aprobar_hechos_perfil",
                         {"ids": args.ids, "todos": args.todos}, n)
    print(f"{n} hecho(s) aprobado(s).")
    print("Si la persona ya es cliente:  python -m app.ingesta_perfiles buscar \"NOMBRE\"")
    print("                              python -m app.ingesta_perfiles vincular \"NOMBRE\" CLAVE")
    print("Si todavía no está en clientes:  python -m app.ingesta_perfiles incorporar \"NOMBRE\"")


def cmd_descartar(args):
    if not args.ids:
        raise SystemExit("Indica los ids. Ejemplo: python -m app.ingesta_perfiles descartar 9 10")
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE public.hechos_perfil
                           SET descartado = TRUE, fecha_actualizacion = now()
                           WHERE id_hecho = ANY(%s) AND activo = FALSE AND descartado = FALSE""",
                        (args.ids,))
            n = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    governance.registrar(_usuario(args), "admin", "descartar_hechos_perfil", {"ids": args.ids}, n)
    print(f"{n} hecho(s) descartado(s). Ya no salen en pendientes ni en los mensajes.")
    if n < len(args.ids):
        print("El resto ya estaba aprobado, descartado o no existe. Un aprobado se queda activo.")


def _resolver_nombre(texto):
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT DISTINCT nombre FROM public.hechos_perfil
                           WHERE LOWER(nombre) = LOWER(%s) OR nombre ILIKE %s
                           ORDER BY nombre""", (texto.strip(), f"%{texto.strip()}%"))
            nombres = [fila[0] for fila in cur.fetchall()]
    finally:
        conn.close()
    if not nombres:
        raise SystemExit(f"No hay hechos de perfil para '{texto}'.")
    exactos = [n for n in nombres if n.lower() == texto.strip().lower()]
    if exactos:
        return exactos[0]
    if len(nombres) == 1:
        return nombres[0]
    raise SystemExit("Hay varias personas. Usa el nombre completo: " + ", ".join(nombres))


def _hechos_de(nombre, solo_activos):
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT categoria, titulo, contenido, clave_cliente, activo
                           FROM public.hechos_perfil
                           WHERE LOWER(nombre) = LOWER(%s) AND (%s = FALSE OR activo)
                           ORDER BY id_hecho""", (nombre, solo_activos))
            return [{"categoria": c, "titulo": t, "contenido": x, "clave_cliente": k, "activo": a}
                    for c, t, x, k, a in cur.fetchall()]
    finally:
        conn.close()


def _clientes_por_nombre(texto):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT clave_cliente, nombre, ciudad, profesion, universidad, producto_interes,
                                  tiene_correo, tiene_celular, correo, celular
                           FROM public.clientes_segmentados
                           WHERE nombre ILIKE %s OR clave_cliente = %s OR correo = LOWER(%s) OR celular = %s
                           ORDER BY nombre LIMIT 8""",
                        (f"%{texto.strip()}%", texto.strip(), texto.strip(),
                         perfil_redes.normalizar_celular(texto)))
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def cmd_buscar(args):
    clientes = _clientes_por_nombre(args.nombre)
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT nombre, clave_cliente, COUNT(*),
                                  COUNT(*) FILTER (WHERE activo)
                           FROM public.hechos_perfil
                           WHERE nombre ILIKE %s
                           GROUP BY 1, 2 ORDER BY 1""", (f"%{args.nombre.strip()}%",))
            hechos = cur.fetchall()
    finally:
        conn.close()
    if not hechos:
        print(f"No hay hechos de perfil para '{args.nombre}'.")
    for nombre, clave, total, activos in hechos:
        print(f"Hechos de {nombre}: {total} ({activos} aprobados). Clave actual: {clave or 'sin vincular'}.")
    if not clientes:
        print("Ese nombre no está en clientes. No hay clave todavía.")
        print(f'Créala con:  python -m app.ingesta_perfiles incorporar "{args.nombre}"')
        return
    print("Clientes que coinciden:")
    for c in clientes:
        canal = "correo" if c["tiene_correo"] else ("whatsapp" if c["tiene_celular"] else "sin canal")
        print(f"  {c['clave_cliente']} | {c['nombre']} | {c['producto_interes'] or 'sin producto'} | {canal}")
    print(f'Vincula con:    python -m app.ingesta_perfiles vincular "{args.nombre}" CLAVE')
    print(f'Completa vacíos: python -m app.ingesta_perfiles completar "{args.nombre}" --clave CLAVE')


def cmd_vincular(args):
    args.nombre = _resolver_nombre(args.nombre)
    clave = args.clave.strip()
    # Se acepta la clave (CL000123), el correo o el celular; lo que se guarda es siempre la clave.
    clientes = [c for c in _clientes_por_nombre(clave)
                if clave == c["clave_cliente"] or clave.lower() == c["correo"]
                or (c["celular"] and perfil_redes.normalizar_celular(clave) == c["celular"])]
    if not clientes:
        raise SystemExit(f"No existe un cliente con clave '{clave}'. Búscalo con: buscar \"NOMBRE\"")
    clave = clientes[0]["clave_cliente"]
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE public.hechos_perfil
                           SET clave_cliente = %s, fecha_actualizacion = now()
                           WHERE LOWER(nombre) = LOWER(%s)""", (clave, args.nombre))
            n = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    if not n:
        raise SystemExit(f"No hay hechos a nombre de '{args.nombre}'.")
    governance.registrar(_usuario(args), "admin", "vincular_hechos_perfil",
                         {"nombre": args.nombre, "clave": clave}, n)
    print(f"{n} hecho(s) de {args.nombre} quedaron con la clave {clave} ({clientes[0]['nombre']}).")
    print("El asesor los usa al pedir un mensaje para ese cliente, si los hechos están aprobados.")


def _fila_completa(clave=None, nombre=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if clave:      # la clave estable, o el correo / celular del cliente
                cur.execute("""SELECT clave_cliente, nombre, id_registro_origen, correo, celular,
                                      ciudad, profesion, universidad, producto_interes
                               FROM public.clientes_consolidados
                               WHERE clave_cliente = %s OR correo = LOWER(%s) OR celular = %s""",
                            (clave, clave, perfil_redes.normalizar_celular(clave)))
            else:
                cur.execute("""SELECT clave_cliente, nombre, id_registro_origen, correo, celular,
                                      ciudad, profesion, universidad, producto_interes
                               FROM public.clientes_consolidados WHERE nombre ILIKE %s
                               ORDER BY nombre LIMIT 8""", (f"%{nombre.strip()}%",))
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def _vacio(valor):
    return valor is None or not str(valor).strip()


def cmd_completar(args):
    """Llena campos vacíos de un cliente que ya existe. No crea otro registro ni pisa lo que ya está."""
    args.nombre = _resolver_nombre(args.nombre)
    clave = (args.clave or "").strip()
    if clave:
        candidatos = _fila_completa(clave=clave)
        if not candidatos:
            raise SystemExit(f"No existe un cliente con clave '{clave}'.")
    else:
        candidatos = _fila_completa(nombre=args.nombre)
        if not candidatos:
            raise SystemExit("Ese nombre no está en clientes. Para crearlo: incorporar \"NOMBRE\".")
        if len(candidatos) > 1:
            print("Hay varios clientes. Indica la clave:")
            for c in candidatos:
                print(f"  {c['clave_cliente']} | {c['nombre']}")
            raise SystemExit(f'python -m app.ingesta_perfiles completar "{args.nombre}" --clave CLAVE')
    cliente = candidatos[0]
    hechos = _hechos_de(args.nombre, solo_activos=True)
    if not hechos:
        raise SystemExit("No hay hechos aprobados. Aprueba el contacto y los demás datos antes de completar.")
    datos = perfil_redes.datos_para_cliente(hechos)
    campos = ("correo", "celular", "ciudad", "profesion", "universidad", "producto_interes")
    nuevos = {campo: datos[campo] for campo in campos if datos.get(campo) and _vacio(cliente[campo])}
    ya = [campo for campo in campos if datos.get(campo) and not _vacio(cliente[campo])]
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if nuevos:
                asignaciones = ", ".join(f"{campo} = %s" for campo in nuevos)
                cur.execute(f"""UPDATE public.clientes SET {asignaciones}
                                WHERE id_registro = %s""",
                            list(nuevos.values()) + [cliente["id_registro_origen"]])
            cur.execute("""UPDATE public.hechos_perfil
                           SET clave_cliente = %s, fecha_actualizacion = now()
                           WHERE LOWER(nombre) = LOWER(%s)""",
                        (cliente["clave_cliente"], args.nombre))
            cur.execute("""SELECT clave_cliente FROM public.clientes_consolidados
                           WHERE id_registro_origen = %s""", (cliente["id_registro_origen"],))
            fila = cur.fetchone()
            clave_nueva = fila[0] if fila else cliente["clave_cliente"]
            if clave_nueva != cliente["clave_cliente"]:
                cur.execute("""UPDATE public.hechos_perfil SET clave_cliente = %s, fecha_actualizacion = now()
                               WHERE clave_cliente = %s OR LOWER(nombre) = LOWER(%s)""",
                            (clave_nueva, cliente["clave_cliente"], args.nombre))
        conn.commit()
    finally:
        conn.close()
    governance.registrar(_usuario(args), "admin", "completar_cliente",
                         {"nombre": args.nombre, "clave": clave_nueva, "campos": list(nuevos)}, len(nuevos))
    print(f"{args.nombre} quedó con el cliente {cliente['nombre']} (clave {clave_nueva}).")
    if nuevos:
        for campo, valor in nuevos.items():
            print(f"  {campo}: se completó con {valor}")
    else:
        print("  No había campos vacíos que el perfil pudiera llenar.")
    if ya:
        print("  Ya tenían dato y no se cambiaron: " + ", ".join(ya))
    if clave_nueva != cliente["clave_cliente"]:
        print(f"  La clave pasó de {cliente['clave_cliente']} a {clave_nueva} porque el contacto nuevo es la clave.")


def cmd_incorporar(args):
    """Crea el cliente que todavía no existe y le pone la clave a los hechos aprobados."""
    args.nombre = _resolver_nombre(args.nombre)
    ya = _clientes_por_nombre(args.nombre)
    if ya:
        print("Ese nombre ya parece un cliente. No creé otro registro.")
        for c in ya:
            print(f"  {c['clave_cliente']} | {c['nombre']}")
        print(f'Usa:  python -m app.ingesta_perfiles vincular "{args.nombre}" CLAVE')
        return
    hechos = _hechos_de(args.nombre, solo_activos=True)
    if not hechos:
        raise SystemExit("No hay hechos aprobados para esa persona. Primero: aprobar ID...")
    datos = perfil_redes.datos_para_cliente(hechos)
    producto = (args.producto or datos["producto_interes"] or "").strip()
    if not producto:
        raise SystemExit("Aprueba un 'Producto sugerido' o pasa --producto \"Seguro educativo\".")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO public.clientes
                           (nombre, ciudad, profesion, universidad, producto_interes, tipo_base)
                           VALUES (%s,%s,%s,%s,%s,'Prospecto') RETURNING id_registro""",
                        (args.nombre, datos["ciudad"], datos["profesion"], datos["universidad"], producto))
            nuevo = cur.fetchone()
            if nuevo is None:
                conn.rollback()
                raise SystemExit("No se pudo crear el cliente.")
            id_registro = nuevo[0]
            cur.execute("""SELECT clave_cliente FROM public.clientes_consolidados
                           WHERE id_registro_origen = %s""", (id_registro,))
            fila = cur.fetchone()
            clave = fila[0] if fila else str(id_registro)
            cur.execute("""UPDATE public.hechos_perfil
                           SET clave_cliente = %s, fecha_actualizacion = now()
                           WHERE LOWER(nombre) = LOWER(%s)""", (clave, args.nombre))
        conn.commit()
    finally:
        conn.close()
    governance.registrar(_usuario(args), "admin", "incorporar_perfil",
                         {"nombre": args.nombre, "clave": clave, "producto": producto}, 1)
    print(f"Cliente creado. Clave: {clave}")
    print(f"  Producto: {producto}")
    print(f"  Ciudad: {datos['ciudad'] or '—'}")
    print(f"  Profesión: {datos['profesion'] or '—'}")
    print(f"  Universidad: {datos['universidad'] or '—'}")
    print("Todavía no tiene correo ni celular, así que el asesor no puede armar WhatsApp ni correo")
    print("hasta que ese contacto se cargue en clientes.")
    print(f"Luego, como asesor:  mensaje de whatsapp para {args.nombre}")


def cmd_oferta(args):
    args.nombre = _resolver_nombre(args.nombre)
    hechos = _hechos_de(args.nombre, solo_activos=True)
    if not hechos:
        raise SystemExit("No hay hechos aprobados. Revísalos con pendientes y aprobar.")
    clave = next((h["clave_cliente"] for h in hechos if h["clave_cliente"]), None)
    datos = perfil_redes.datos_para_cliente(hechos)
    print(f"{args.nombre} | clave: {clave or 'sin vincular'}")
    print(f"Producto para ofrecer: {datos['producto_interes'] or 'sin sugerencia aprobada'}")
    for h in hechos:
        if h["categoria"] == "Producto sugerido":
            print(f"  Sugerido: {h['titulo']} — {h['contenido']}")
        else:
            print(f"  {h['categoria']}: {h['contenido']}")
    if not clave:
        print("Falta vincular o incorporar antes de que el asesor redacte.")
        return
    clientes = [c for c in _clientes_por_nombre(clave) if c["clave_cliente"] == clave]
    if not clientes:
        print("La clave no está en clientes. Vuelve a vincular.")
        return
    c = clientes[0]
    if c["tiene_celular"]:
        print(f"Asesor: mensaje de whatsapp para {c['nombre']}")
    elif c["tiene_correo"]:
        print(f"Asesor: mensaje de correo para {c['nombre']}")
    else:
        print("El cliente no tiene correo ni celular. El asesor lo encuentra, pero no arma el borrador.")
    print("El analista no ve esta ficha: solo cuenta y resume grupos de clientes.")


def hechos_explicitos(clave, nombre):
    """Hechos de vida ya aprobados. Vacío si la tabla aún no existe."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT categoria, contenido FROM public.hechos_perfil
                           WHERE activo AND categoria = ANY(%s)
                             AND (
                               (%s <> '' AND clave_cliente = %s)
                               OR (clave_cliente IS NULL AND LOWER(nombre) = LOWER(%s))
                             )
                           ORDER BY id_hecho""",
                        (list(CATEGORIAS_DE_VIDA), clave or "", clave or "", nombre or ""))
            return [{"categoria": c, "contenido": x} for c, x in cur.fetchall()]
    except Exception:
        conn.rollback()
        return []
    finally:
        conn.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ingesta de perfiles públicos autorizados")
    sub = ap.add_subparsers(dest="cmd", required=False)

    s = sub.add_parser("perfiles", help="lee el JSON y scrapea los perfiles autorizados")
    s.add_argument("--archivo", default=str(ARCHIVO))
    s.set_defaults(fn=cmd_perfiles)

    sub.add_parser("resumen", help="conteo por persona y categoría").set_defaults(fn=cmd_resumen)
    p = sub.add_parser("pendientes")
    p.add_argument("--nombre", default="")
    p.add_argument("--limite", type=int, default=40)
    p.set_defaults(fn=cmd_pendientes)
    v = sub.add_parser("ver")
    v.add_argument("id", type=int)
    v.set_defaults(fn=cmd_ver)
    a = sub.add_parser("aprobar")
    a.add_argument("ids", nargs="*", type=int)
    a.add_argument("--todos", action="store_true")
    a.set_defaults(fn=cmd_aprobar)
    d = sub.add_parser("descartar", help="quita pendientes para que no se usen ni vuelvan a listarse")
    d.add_argument("ids", nargs="+", type=int)
    d.set_defaults(fn=cmd_descartar)
    b = sub.add_parser("buscar", help="ve si el nombre ya es cliente y cuál es su clave")
    b.add_argument("nombre")
    b.set_defaults(fn=cmd_buscar)
    vi = sub.add_parser("vincular", help="escribe la clave del cliente en sus hechos")
    vi.add_argument("nombre")
    vi.add_argument("clave")
    vi.set_defaults(fn=cmd_vincular)
    comp = sub.add_parser("completar", help="llena campos vacíos de un cliente que ya existe")
    comp.add_argument("nombre")
    comp.add_argument("--clave", default="")
    comp.set_defaults(fn=cmd_completar)
    inc = sub.add_parser("incorporar", help="crea el cliente si todavía no existe")
    inc.add_argument("nombre")
    inc.add_argument("--producto", default="")
    inc.set_defaults(fn=cmd_incorporar)
    of = sub.add_parser("oferta", help="muestra qué seguro ofrecer con los hechos aprobados")
    of.add_argument("nombre")
    of.set_defaults(fn=cmd_oferta)

    args = ap.parse_args(argv)
    if not getattr(args, "fn", None):
        args.fn = cmd_perfiles
        args.archivo = str(ARCHIVO)
    args.fn(args)


if __name__ == "__main__":
    main()
