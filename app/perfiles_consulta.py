"""Personas con scraping que no están vinculadas a un cliente.

Las cifras y los campos salen de hechos_perfil. Si un dato no está en un hecho, no se inventa.
"""
import re

from app.database import get_connection
from app.perfil_redes import _n, ciudad_usable, datos_para_cliente

FILTROS = {"nombre", "ciudad", "profesion", "producto_interes", "red", "universidad"}
DIMENSIONES = {"red", "ciudad", "profesion", "producto_interes", "universidad"}

_EDAD = re.compile(r"\b(\d{1,3})\b")


def _edad(texto):
    m = _EDAD.search(str(texto or ""))
    if not m:
        return None
    n = int(m.group(1))
    return n if 15 <= n <= 100 else None


def armar_fichas(filas):
    """Una ficha por persona, solo con lo que dicen sus hechos."""
    grupos = {}
    for fila in filas or []:
        clave = _n(fila.get("nombre") or "")
        if not clave:
            continue
        grupos.setdefault(clave, []).append(fila)
    fichas = []
    for hechos in grupos.values():
        nombre = max((h.get("nombre") or "" for h in hechos), key=len)
        datos = datos_para_cliente(hechos)
        redes = sorted({h.get("red") for h in hechos if h.get("red")})
        url = next((h.get("fuente_url") for h in hechos if h.get("fuente_url")), "")
        edad = ingresos = None
        productos = []
        for h in hechos:
            if h.get("categoria") == "Edad" and edad is None:
                edad = _edad(h.get("contenido"))
            if h.get("categoria") == "Ingresos" and not ingresos:
                ingresos = (h.get("contenido") or "").strip() or None
            if h.get("categoria") == "Producto sugerido" and h.get("titulo"):
                if h["titulo"] not in productos:
                    productos.append(h["titulo"])
        fichas.append({
            "nombre": nombre,
            "clave_cliente": None,
            "genero": None,
            "edad": edad,
            "ciudad": datos.get("ciudad"),
            "profesion": datos.get("profesion"),
            "universidad": datos.get("universidad"),
            "producto_interes": ", ".join(productos) or datos.get("producto_interes"),
            "segmento": ", ".join(redes) if redes else None,
            "correo": datos.get("correo"),
            "celular": datos.get("celular"),
            "red": ", ".join(redes),
            "redes": ", ".join(redes),
            "fuente_url": url,
            "ingresos": ingresos,
        })
    fichas.sort(key=lambda f: _n(f["nombre"]))
    return fichas


def _coincide(ficha, filtros, nombre=""):
    pedido = dict(filtros or {})
    if nombre:
        pedido["nombre"] = nombre
    for campo, valor in pedido.items():
        if campo not in FILTROS or valor in (None, ""):
            continue
        dato = ficha.get("redes") if campo == "red" else ficha.get(campo)
        if _n(valor) not in _n(dato or ""):
            return False
    return True


def filtrar(fichas, filtros=None, nombre=""):
    return [f for f in fichas if _coincide(f, filtros, nombre)]


def contar(fichas, dimension):
    if dimension not in DIMENSIONES:
        return [("sin vincular", len(fichas))]
    grupos = {}
    for ficha in fichas:
        clave = ficha.get(dimension) or "sin_dato"
        grupos[clave] = grupos.get(clave, 0) + 1
    return sorted(grupos.items(), key=lambda par: (-par[1], par[0]))


def resumen(fichas):
    edades = [f["edad"] for f in fichas if isinstance(f.get("edad"), int)]
    promedio = round(sum(edades) / len(edades), 1) if edades else None
    return {
        "total": len(fichas),
        "edad_promedio": promedio,
        "top_ciudad": contar(fichas, "ciudad")[:3],
        "top_profesion": contar(fichas, "profesion")[:3],
        "top_producto_interes": contar(fichas, "producto_interes")[:3],
        "etiqueta": "Perfiles sin vincular",
        "nota": "Personas a las que se les hizo scraping y no están en la lista de clientes.",
    }


def texto(ficha):
    """Lo que el asesor puede leer. El salario solo si la persona lo publicó."""
    if not ficha:
        return "No está en la lista de clientes ni hay scraping de esa persona."
    lineas = [f"{ficha['nombre']} no está vinculado a la lista de clientes. Del scraping consta:"]
    campos = (
        ("Red", "redes"), ("Ciudad", "ciudad"), ("Profesión", "profesion"),
        ("Estudios", "universidad"), ("Edad", "edad"),
        ("Producto sugerido", "producto_interes"), ("Correo", "correo"),
        ("Celular", "celular"),
    )
    hubo = False
    for etiqueta, clave in campos:
        valor = ficha.get(clave)
        if valor not in (None, ""):
            lineas.append(f"{etiqueta}: {valor}.")
            hubo = True
    if ficha.get("ingresos"):
        lineas.append(f"Ingresos publicados: {ficha['ingresos']}.")
        hubo = True
    if ficha.get("fuente_url"):
        lineas.append(f"Perfil: {ficha['fuente_url']}")
    if not hubo:
        lineas.append("No quedó ciudad, trabajo, estudios, edad ni producto en la ficha.")
    return " ".join(lineas)


def cargar():
    from app.ingesta_perfiles import asegurar_tabla
    asegurar_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT nombre, red, fuente_url, categoria, titulo, contenido
                FROM public.hechos_perfil
                WHERE NOT descartado
                  AND nombre IN (
                    SELECT nombre FROM public.hechos_perfil
                    GROUP BY nombre
                    HAVING MAX(NULLIF(btrim(clave_cliente), '')) IS NULL
                  )
                ORDER BY nombre, id_hecho
            """)
            cols = [d[0] for d in cur.description]
            filas = [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()
    return armar_fichas(filas)


def consultar(filtros=None, nombre="", limite=50):
    fichas = filtrar(cargar(), filtros, nombre)
    return fichas[: int(limite)], len(fichas)


def diagnostico(filtros=None):
    todas = cargar()
    filas = [{"filtro": "Sin filtros (perfiles con scraping, sin vincular)", "n": len(todas)}]
    for campo, valor in (filtros or {}).items():
        if campo in FILTROS:
            filas.append({"filtro": f"Solo {campo} = {valor}", "n": len(filtrar(todas, {campo: valor}))})
    return filas
