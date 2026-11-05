"""Capa de adquisición de LinkedIn: perfil público autorizado -> publicaciones -> intereses -> revisión.

Solo abre la URL pública que está en data/perfiles_autorizados.json. Si LinkedIn muestra
inicio de sesión, la página se deja. El texto de política o religión no se guarda; el
salario sí, como señal de ingresos del perfil.
El interés queda pendiente hasta que un administrador lo aprueba; solo entonces pasa al perfil.

  python -m app.ingesta_linkedin leer
  python -m app.ingesta_linkedin leer --nombre "Ana Gómez"
  python -m app.ingesta_linkedin desde-html pagina.html --url https://www.linkedin.com/in/ana
  python -m app.ingesta_linkedin resumen | pendientes | ver ID | aprobar ID... | descartar ID...

La pausa entre perfiles es fija (LINKEDIN_PAUSA, segundos). El navegador es Chrome normal:
no carga cookies y no modifica la marca de automatización. La página pública se recorre con
scroll en pasos (LINKEDIN_SCROLL_PASOS / LINKEDIN_SCROLL_PAUSA / LINKEDIN_SCROLL_PX) para
cargar las publicaciones diferidas; si aparece el muro de acceso, la página se deja.
"""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

from app import governance, linkedin_texto
from app.database import get_connection
from app.ingesta_perfiles import ARCHIVO, asegurar_tabla as asegurar_hechos

PAUSA = float(os.getenv("LINKEDIN_PAUSA", "2"))
MAX_POSTS = int(os.getenv("LINKEDIN_MAX_POSTS", "10"))
SCROLL_PASOS = int(os.getenv("LINKEDIN_SCROLL_PASOS", "4"))
SCROLL_PAUSA = float(os.getenv("LINKEDIN_SCROLL_PAUSA", "1.5"))
SCROLL_PX = int(os.getenv("LINKEDIN_SCROLL_PX", "900"))

DDL = """
CREATE TABLE IF NOT EXISTS public.publicaciones_linkedin (
    id_publicacion SERIAL PRIMARY KEY,
    clave_cliente TEXT,
    nombre TEXT NOT NULL,
    fuente_url TEXT NOT NULL,
    urn TEXT,
    texto TEXT NOT NULL,
    tiempo TEXT,
    hash_contenido TEXT NOT NULL,
    fecha_extraccion TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS publicaciones_linkedin_fuente_hash
    ON public.publicaciones_linkedin (fuente_url, hash_contenido);
CREATE TABLE IF NOT EXISTS public.intereses_linkedin (
    id_interes SERIAL PRIMARY KEY,
    id_publicacion INTEGER REFERENCES public.publicaciones_linkedin (id_publicacion) ON DELETE CASCADE,
    clave_cliente TEXT,
    nombre TEXT NOT NULL,
    fuente_url TEXT NOT NULL,
    tema TEXT NOT NULL,
    producto TEXT NOT NULL,
    razon TEXT NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT FALSE,
    descartado BOOLEAN NOT NULL DEFAULT FALSE,
    id_hecho INTEGER,
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS intereses_linkedin_unicos
    ON public.intereses_linkedin (id_publicacion, tema, producto);
ALTER TABLE public.publicaciones_linkedin ADD COLUMN IF NOT EXISTS red TEXT NOT NULL DEFAULT 'linkedin';
ALTER TABLE public.intereses_linkedin ADD COLUMN IF NOT EXISTS red TEXT NOT NULL DEFAULT 'linkedin';
ALTER TABLE public.publicaciones_linkedin ADD COLUMN IF NOT EXISTS url_publicacion TEXT NOT NULL DEFAULT '';
ALTER TABLE public.publicaciones_linkedin ADD COLUMN IF NOT EXISTS tipo TEXT NOT NULL DEFAULT 'publicacion';
ALTER TABLE public.publicaciones_linkedin ADD COLUMN IF NOT EXISTS resumen TEXT NOT NULL DEFAULT '';
ALTER TABLE public.publicaciones_linkedin ADD COLUMN IF NOT EXISTS tiene_imagenes BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE public.publicaciones_linkedin ADD COLUMN IF NOT EXISTS n_imagenes INTEGER NOT NULL DEFAULT 0;
"""


def _usuario(args=None):
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


def _cargar_lista(ruta):
    archivo = Path(ruta)
    if not archivo.is_file():
        raise SystemExit(f"No existe {archivo}. Registra primero a quien autorizó la lectura.")
    data = json.loads(archivo.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("El archivo de autorizados tiene que ser una lista.")
    return data


def _abrir_navegador():
    """Chrome visible, sin cookies y sin ocultar que es un navegador automatizado."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    opciones = Options()
    opciones.add_argument("--window-size=1280,900")
    return webdriver.Chrome(options=opciones)


def _scroll_para_lazy_load(driver):
    """Baja la página pública en pasos para que carguen las publicaciones diferidas.

    Se detiene si aparece el muro de acceso o cuando un scroll ya no trae elementos nuevos.
    """
    from selenium.webdriver.common.by import By

    cargados = 0
    for _ in range(SCROLL_PASOS):
        if "authwall" in (driver.page_source or "").lower() or "/login" in (driver.current_url or "").lower():
            break
        driver.execute_script("window.scrollBy(0, arguments[0]);", SCROLL_PX)
        time.sleep(SCROLL_PAUSA)
        nuevos = len(driver.find_elements(By.CSS_SELECTOR, "[data-urn]"))
        if nuevos <= cargados:
            break
        cargados = nuevos


def _html_publico(driver, url):
    """HTML de la página pública del perfil. Espera las publicaciones (data-urn) y hace scroll
    para el contenido diferido. Si LinkedIn muestra el muro de acceso, no insiste."""
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    driver.get(url)
    WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    def lista_o_muro(d):
        if "/login" in (d.current_url or "").lower() or "authwall" in d.page_source.lower():
            return True
        return d.find_elements(By.CSS_SELECTOR, "[data-urn]") or "urn:li:activity" in d.page_source

    try:
        WebDriverWait(driver, 8).until(lista_o_muro)
    except TimeoutException:
        pass
    _scroll_para_lazy_load(driver)
    return driver.page_source or "", driver.current_url or url


def _guardar_publicacion(persona, url, post, red="linkedin"):
    """-> id_publicacion. None si ese texto ya estaba guardado para esa URL."""
    h = hashlib.sha256(post["texto"].encode("utf-8")).hexdigest()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id_publicacion FROM public.publicaciones_linkedin
                           WHERE fuente_url = %s AND hash_contenido = %s""", (url, h))
            fila = cur.fetchone()
            if fila:
                return fila[0], False
            cur.execute("""INSERT INTO public.publicaciones_linkedin
                           (clave_cliente, nombre, fuente_url, urn, texto, tiempo, hash_contenido, red,
                            url_publicacion, tipo, resumen, tiene_imagenes, n_imagenes)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id_publicacion""",
                        (persona.get("clave_cliente"), persona["nombre"], url,
                         post.get("urn") or None, post["texto"], post.get("tiempo") or None, h, red,
                         (post.get("url_publicacion") or post.get("url") or "")[:500],
                         (post.get("tipo") or "publicacion")[:40],
                         (post.get("resumen") or "")[:500],
                         bool(post.get("tiene_imagenes")),
                         int(post.get("n_imagenes") or 0)))
            nuevo = cur.fetchone()[0]
        conn.commit()
        return nuevo, True
    finally:
        conn.close()


def _guardar_interes(id_publicacion, persona, url, interes, red="linkedin"):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO public.intereses_linkedin
                           (id_publicacion, clave_cliente, nombre, fuente_url, tema, producto, razon, red)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (id_publicacion, tema, producto) DO NOTHING""",
                        (id_publicacion, persona.get("clave_cliente"), persona["nombre"], url,
                         interes["tema"], interes["producto"], interes["razon"], red))
            nuevo = cur.rowcount
        conn.commit()
        return nuevo
    finally:
        conn.close()


def procesar_html(html, url, persona, url_final=""):
    """Guarda publicaciones e intereses pendientes. Devuelve un resumen. Lo sensible no se guarda."""
    if linkedin_texto.pagina_es_muro(html, url_final):
        print(f"✗ {url}: LinkedIn mostró inicio de sesión. La página no se lee.")
        return {"muro": True, "publicaciones": 0, "intereses": 0, "omitidas": 0}
    posts = linkedin_texto.extraer_publicaciones(html, MAX_POSTS)
    if not posts:
        print(f"⚠ {url}: la página pública no mostró publicaciones.")
        return {"muro": False, "publicaciones": 0, "intereses": 0, "omitidas": 0}
    asegurar_tabla()
    nuevas = intereses = omitidas = 0
    for post in posts:
        evaluacion = linkedin_texto.evaluar_publicacion(post["texto"])
        if evaluacion["omitida"]:
            omitidas += 1
            print(f"   omitida ({evaluacion['motivo']}): el texto no se guarda.")
            continue
        id_publicacion, es_nueva = _guardar_publicacion(persona, url, post)
        nuevas += int(es_nueva)
        for interes in evaluacion["intereses"]:
            intereses += _guardar_interes(id_publicacion, persona, url, interes)
    print(f"✓ {url}: {nuevas} publicaciones nuevas, {intereses} intereses pendientes, {omitidas} omitidas.")
    return {"muro": False, "publicaciones": nuevas, "intereses": intereses, "omitidas": omitidas}


def leer(nombres=None, tarea=None, usuario=None, archivo=None):
    """Abre cada perfil público autorizado. Sin autorización, no abre nada."""
    data = _cargar_lista(archivo or ARCHIVO)
    personas, avisos = linkedin_texto.personas_linkedin(data)
    for aviso in avisos:
        print(f"· {aviso}")
    if nombres:
        pedidas = {n.strip().lower() for n in nombres if n and n.strip()}
        personas = [p for p in personas if p["nombre"].lower() in pedidas]
        faltan = pedidas - {p["nombre"].lower() for p in personas}
        for nombre in sorted(faltan):
            print(f"✗ {nombre}: no está autorizado o no tiene un perfil público de LinkedIn.")
    objetivos = [(p, u["url"]) for p in personas for u in p["urls"]]
    if not objetivos:
        print("No hay perfiles públicos de LinkedIn autorizados para leer.")
        return {"perfiles": 0, "intereses": 0}
    if tarea is not None:
        tarea.avance(0, len(objetivos))
    governance.registrar(usuario or _usuario(), "admin", "leer_linkedin",
                         {"perfiles": [u for _, u in objetivos]}, len(objetivos))
    intereses = 0
    driver = None
    try:
        driver = _abrir_navegador()
        for i, (persona, url) in enumerate(objetivos, 1):
            print(f"\n--- {persona['nombre']}: {url} ---")
            html, final = _html_publico(driver, url)
            intereses += procesar_html(html, url, persona, final)["intereses"]
            if tarea is not None:
                tarea.avance(i, len(objetivos))
            if i < len(objetivos) and PAUSA > 0:
                time.sleep(PAUSA)
    finally:
        if driver is not None:
            driver.quit()
    print("\nRevisa con:  python -m app.ingesta_linkedin pendientes")
    return {"perfiles": len(objetivos), "intereses": intereses}


def cmd_leer(args):
    leer(nombres=[args.nombre] if getattr(args, "nombre", "") else None,
         usuario=_usuario(args), archivo=getattr(args, "archivo", None) or str(ARCHIVO))


def cmd_desde_html(args):
    data = _cargar_lista(getattr(args, "archivo", None) or ARCHIVO)
    personas, avisos = linkedin_texto.personas_linkedin(data)
    for aviso in avisos:
        print(f"· {aviso}")
    persona = linkedin_texto.persona_de_url(args.url, personas)
    if not persona:
        raise SystemExit("Sin autorización no se lee. La URL tiene que ser el perfil público "
                         "(/in/…) de alguien con autorizado = true.")
    html = Path(args.html).read_text(encoding="utf-8")
    procesar_html(html, persona["url"], persona)
    governance.registrar(_usuario(args), "admin", "leer_linkedin_html", {"url": persona["url"]}, 1)


def cmd_resumen(_):
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT nombre,
                                  COUNT(*) FILTER (WHERE NOT activo AND NOT descartado),
                                  COUNT(*) FILTER (WHERE activo),
                                  COUNT(*) FILTER (WHERE descartado AND NOT activo)
                           FROM public.intereses_linkedin GROUP BY nombre ORDER BY nombre""")
            filas = cur.fetchall()
    finally:
        conn.close()
    if not filas:
        print("Aún no hay intereses de LinkedIn.")
        return
    print(f"{'Persona':32} {'Pendientes':>10} {'Aprobados':>9} {'Descartados':>12}")
    for nombre, pend, act, desc in filas:
        print(f"{nombre:32} {pend:>10} {act:>9} {desc:>12}")


def cmd_pendientes(args):
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            where, params = ["NOT activo", "NOT descartado"], []
            if args.nombre:
                where.append("LOWER(nombre) = LOWER(%s)")
                params.append(args.nombre)
            cur.execute(f"""SELECT id_interes, nombre, tema, producto, razon
                            FROM public.intereses_linkedin WHERE {' AND '.join(where)}
                            ORDER BY id_interes LIMIT %s""", params + [args.limite])
            filas = cur.fetchall()
    finally:
        conn.close()
    if not filas:
        print("No hay intereses pendientes.")
    for f in filas:
        print(f"#{f[0]} | {f[1]} | {f[2]} | {f[3]}\n     {f[4]}")


def cmd_ver(args):
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT i.id_interes, i.nombre, i.tema, i.producto, i.razon, i.activo,
                                  i.descartado, i.fuente_url, p.texto, p.tiempo
                           FROM public.intereses_linkedin i
                           JOIN public.publicaciones_linkedin p USING (id_publicacion)
                           WHERE i.id_interes = %s""", (args.id,))
            f = cur.fetchone()
    finally:
        conn.close()
    if not f:
        raise SystemExit("No existe.")
    print(f"#{f[0]} | {f[1]} | {f[2]} | {f[3]} | activo={f[5]} | descartado={f[6]}\n"
          f"{f[4]}\nFuente: {f[7]}\nTiempo: {f[9] or '—'}\n\n{f[8]}")


def _pasar_al_perfil(cur, fila):
    """Copia el interés ya aprobado a hechos_perfil. Devuelve id_hecho."""
    asegurar_hechos()
    titulo = f"Interes: {fila['producto']} ({fila['tema']})"
    cuerpo = f"{fila['producto']}: {fila['razon']}"
    h = hashlib.sha256(cuerpo.encode("utf-8")).hexdigest()
    cur.execute("""SELECT id_hecho FROM public.hechos_perfil
                   WHERE fuente_url = %s AND titulo = %s""", (fila["fuente_url"], titulo))
    ya = cur.fetchone()
    if ya:
        cur.execute("""UPDATE public.hechos_perfil
                       SET contenido = %s, hash_contenido = %s, activo = TRUE, descartado = FALSE,
                           clave_cliente = COALESCE(%s, clave_cliente), fecha_actualizacion = now()
                       WHERE id_hecho = %s""",
                    (cuerpo, h, fila["clave_cliente"], ya[0]))
        return ya[0]
    cur.execute("""INSERT INTO public.hechos_perfil
                   (clave_cliente, nombre, red, fuente_url, categoria, titulo, contenido,
                    hash_contenido, activo, fecha_actualizacion)
                   VALUES (%s,%s,%s,%s,'Interes',%s,%s,%s,TRUE,now())
                   RETURNING id_hecho""",
                (fila["clave_cliente"], fila["nombre"], fila.get("red") or "linkedin",
                 fila["fuente_url"], titulo, cuerpo, h))
    return cur.fetchone()[0]


def cmd_aprobar(args):
    if not args.ids and not args.todos:
        raise SystemExit("Indica ids, o usa --todos.")
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if args.todos:
                cur.execute("""SELECT id_interes, clave_cliente, nombre, fuente_url, tema, producto, razon, red
                               FROM public.intereses_linkedin
                               WHERE NOT activo AND NOT descartado ORDER BY id_interes""")
            else:
                cur.execute("""SELECT id_interes, clave_cliente, nombre, fuente_url, tema, producto, razon, red
                               FROM public.intereses_linkedin
                               WHERE id_interes = ANY(%s) AND NOT descartado ORDER BY id_interes""", (args.ids,))
            filas = [dict(zip(("id_interes", "clave_cliente", "nombre", "fuente_url", "tema", "producto", "razon", "red"), f))
                     for f in cur.fetchall()]
            for fila in filas:
                id_hecho = _pasar_al_perfil(cur, fila)
                cur.execute("""UPDATE public.intereses_linkedin
                               SET activo = TRUE, descartado = FALSE, id_hecho = %s, fecha_actualizacion = now()
                               WHERE id_interes = %s""", (id_hecho, fila["id_interes"]))
        conn.commit()
    finally:
        conn.close()
    governance.registrar(_usuario(args), "admin", "aprobar_interes_linkedin",
                         {"ids": args.ids, "todos": args.todos}, len(filas))
    print(f"{len(filas)} interés(es) aprobado(s): ya están en el perfil.")


def cmd_descartar(args):
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE public.intereses_linkedin
                           SET descartado = TRUE, activo = FALSE, fecha_actualizacion = now()
                           WHERE id_interes = ANY(%s) AND NOT activo""", (args.ids,))
            n = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    governance.registrar(_usuario(args), "admin", "descartar_interes_linkedin", {"ids": args.ids}, n)
    print(f"{n} interés(es) descartado(s). No pasan al perfil.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Adquisición de publicaciones públicas de LinkedIn autorizadas")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("leer", help="abre los perfiles públicos autorizados")
    s.add_argument("--nombre", default="", help="solo esta persona")
    s.add_argument("--archivo", default=str(ARCHIVO))
    s.set_defaults(fn=cmd_leer)

    h = sub.add_parser("desde-html", help="procesa un HTML ya guardado del perfil público")
    h.add_argument("html")
    h.add_argument("--url", required=True)
    h.add_argument("--archivo", default=str(ARCHIVO))
    h.set_defaults(fn=cmd_desde_html)

    sub.add_parser("resumen").set_defaults(fn=cmd_resumen)
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
    d = sub.add_parser("descartar")
    d.add_argument("ids", nargs="+", type=int)
    d.set_defaults(fn=cmd_descartar)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
