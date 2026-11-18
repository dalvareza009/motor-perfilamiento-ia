"""Perfiles de cliente del catálogo Global 2026 (cartera ene-2021 a oct-2026).

Fuente: presentación interna «Perfil cliente 2026 31-oct». Cada línea de producto
tiene un comprador típico (edad, ciudad, estado civil, hijos, forma de pago).
Se guarda en `conocimiento` para que el motor lo tenga siempre a la mano.
El salario queda como dato interno: no se usa en mensajes al cliente.
"""
import hashlib
import re

from app.database import get_connection
from app.perfil_redes import HIJOS, PAREJA, _n

FUENTE = "catalogo://global/perfil-cliente-2026"
PERIODO = "ene-2021 a oct-2026"

# Cada ítem: producto del catálogo + resumen que sí puede ver el asesor,
# y el detalle salarial solo para la base (categoría interna).
PERFILES = (
    {
        "id": "educativo-garantizada",
        "producto": "Seguro educativo",
        "linea": "GARANTIZADA",
        "polizas": 6519,
        "titulo": "Perfil de cliente 2026 · Educativo GARANTIZADA",
        "resumen": (
            "Compradores típicos de Seguro educativo GARANTIZADA (6.519 pólizas, "
            f"{PERIODO}). Edad al comprar: 31-40 (45%) y 41-50 (41%). "
            "Mayoría casados (76%) o en unión libre (12%). "
            "El beneficiario suele ser un niño de 0 a 12 años (el pico es al nacer o al primer año). "
            "Ciudades: Bogotá (64%), Barranquilla (9%), Medellín (8%), Bucaramanga (7%), Cali (6%). "
            "Género: 57% hombres, 43% mujeres. Pago financiado (70%) más que de contado (30%)."
        ),
        "salario": "Mayor a 20 SMMLV 49%; 13-20 21%; 8-13 17%; 4-8 10%; menor a 4 3%.",
        "edades_compra": {"31-50": 86, "21-30": 3, "51-70": 11},
        "ciudades": ("bogota", "barranquilla", "medellin", "bucaramanga", "cali"),
        "estado_civil": ("casad", "union libre"),
        "hijos": True,
        "edad_beneficiario": "0-12",
    },
    {
        "id": "educativo-profesional-segura",
        "producto": "Seguro educativo",
        "linea": "Profesional y Segura",
        "polizas": 1957,
        "titulo": "Perfil de cliente 2026 · Educativo Profesional y Segura",
        "resumen": (
            "Compradores típicos de Seguro educativo Profesional y Segura (1.957 pólizas, "
            f"{PERIODO}). Edad al comprar: 31-40 (46%) y 41-50 (34%); también 21-30 (10%). "
            "Casados (58%), unión libre (20%) o solteros (16%). "
            "El beneficiario es un niño de 0 a 12 años. "
            "Ciudades: Bogotá (26%) y Medellín (26%), Barranquilla (13%), Cali (12%), Bucaramanga (11%). "
            "Género: 58% mujeres, 42% hombres. En Segura el pago de contado es 73%."
        ),
        "salario": "4-8 SMMLV 26%; 8-13 21%; mayor a 20 19%; menor a 4 18%; 13-20 16%.",
        "edades_compra": {"31-50": 80, "21-30": 10, "51-70": 9},
        "ciudades": ("bogota", "medellin", "barranquilla", "cali", "bucaramanga"),
        "estado_civil": ("casad", "union libre", "solter"),
        "hijos": True,
        "edad_beneficiario": "0-12",
    },
    {
        "id": "vida",
        "producto": "Seguro de vida",
        "linea": "Vida (sin PUG ni INDX)",
        "polizas": 3946,
        "titulo": "Perfil de cliente 2026 · Vida",
        "resumen": (
            "Compradores típicos de Seguro de vida, sin PUG ni INDX (3.946 pólizas, "
            f"{PERIODO}). Edad al comprar: 31-40 (33%), 41-50 (25%) y 21-30 (23%); 51-60 (12%). "
            "Solteros (40%) o casados (35%); unión libre 12%. "
            "Género: 61% mujeres, 39% hombres. "
            "Ciudades: Medellín (38%), Bogotá (20%), Bucaramanga (10%), Barranquilla (10%), Cali (7%)."
        ),
        "salario": "En blanco 30%; menor a 4 SMMLV 29%; 4-8 19%; 8-13 9%; mayor a 20 6%; 13-20 6%.",
        "edades_compra": {"21-30": 23, "31-50": 58, "51-70": 15},
        "ciudades": ("medellin", "bogota", "bucaramanga", "barranquilla", "cali"),
        "estado_civil": ("solter", "casad", "union libre"),
        "hijos": False,
        "edad_beneficiario": "",
    },
    {
        "id": "pensiones",
        "producto": "Seguro de pensión",
        "linea": "Pensiones",
        "polizas": 916,
        "titulo": "Perfil de cliente 2026 · Pensiones",
        "resumen": (
            "Compradores típicos de pensiones (916 pólizas, "
            f"{PERIODO}). Edad al comprar repartida de 21 a 75 años, con más peso entre 26 y 65. "
            "Casados (49%) o solteros (32%). Género: 53% mujeres, 47% hombres. "
            "Ciudades: Bogotá (39%), Medellín (17%), Manizales (14%), Cali (14%), Bucaramanga (8%)."
        ),
        "salario": "En blanco 59%; mayor a 20 SMMLV 15%; 4-8 8%; 13-20 7%; menor a 4 6%; 8-13 5%.",
        "edades_compra": {"21-30": 19, "31-50": 44, "51-70": 32},
        "ciudades": ("bogota", "medellin", "manizales", "cali", "bucaramanga"),
        "estado_civil": ("casad", "solter"),
        "hijos": False,
        "edad_beneficiario": "",
        "tambien": ("Seguro previsional",),
    },
    {
        "id": "rentas-flex",
        "producto": "Seguro renta voluntaria",
        "linea": "Rentas y Flex",
        "polizas": 2047,
        "titulo": "Perfil de cliente 2026 · Rentas y Flex",
        "resumen": (
            "Compradores típicos de rentas y Flex (2.047 pólizas, "
            f"{PERIODO}). Edad al comprar: 41-45 (22%), 36-40 (19%), 31-35 (16%) y 46-50 (15%). "
            "Casados (55%) o solteros (20%); unión libre 14%. "
            "Género: 64% mujeres, 36% hombres. "
            "Ciudades: Bogotá (65%), Cali (11%), Medellín (10%)."
        ),
        "salario": "En blanco 24%; 4-8 SMMLV 20%; menor a 4 18%; mayor a 20 15%; 8-13 14%; 13-20 10%.",
        "edades_compra": {"31-50": 72, "51-70": 19, "21-30": 8},
        "ciudades": ("bogota", "cali", "medellin"),
        "estado_civil": ("casad", "solter", "union libre"),
        "hijos": False,
        "edad_beneficiario": "",
        "tambien": ("Seguro renta vitalicia",),
    },
)

_EDAD = re.compile(r"\b(\d{1,2})\s*anos\b")
_CIUDADES = (
    "bogota", "medellin", "barranquilla", "cali", "bucaramanga",
    "manizales", "cartagena", "pereira", "pasto",
)


def _edad(hechos):
    for h in hechos or []:
        m = _EDAD.search(_n(h.get("contenido") or ""))
        if m and (h.get("categoria") or "") in {"Edad", "Situacion actual", "Descripcion"}:
            n = int(m.group(1))
            if 15 <= n <= 100:
                return n
    return None


def _ciudad(hechos):
    for h in hechos or []:
        n = _n(h.get("contenido") or "")
        if (h.get("categoria") or "") not in {"Ubicacion", "Descripcion", "Situacion actual"}:
            continue
        for c in _CIUDADES:
            if c in n:
                return c
    return None


def _civil(hechos):
    for h in hechos or []:
        if (h.get("categoria") or "") not in {"Estado civil", "Familia"}:
            continue
        n = _n(h.get("contenido") or "")
        if PAREJA.search(n) or "casad" in n or "union libre" in n:
            if "solter" in n:
                continue
            return "casad"
        if "solter" in n:
            return "solter"
        if "union libre" in n:
            return "union libre"
    return ""


def _tiene_hijos(hechos):
    for h in hechos or []:
        cat = h.get("categoria") or ""
        n = _n(h.get("contenido") or "")
        if cat == "Hijos":
            return True
        if cat == "Indicio de hijos":
            continue
        if cat in {"Familia", "Descripcion"} and HIJOS.search(n):
            return True
    return False


def _banda(edad):
    if edad is None:
        return ""
    if edad < 31:
        return "21-30"
    if edad <= 50:
        return "31-50"
    return "51-70"


def fragmentos():
    """Filas para `conocimiento`: perfil (asesor) + dato interno de salario."""
    filas = []
    for p in PERFILES:
        productos = (p["producto"],) + tuple(p.get("tambien") or ())
        for producto in productos:
            filas.append({
                "categoria": "perfil de cliente",
                "producto": producto,
                "titulo": p["titulo"] if producto == p["producto"] else f"{p['titulo']} ({producto})",
                "contenido": p["resumen"],
            })
            filas.append({
                "categoria": "dato interno de cartera",
                "producto": producto,
                "titulo": f"Rango salarial interno · {p['linea']}",
                "contenido": (
                    f"Dato interno de cartera {PERIODO}, no mencionar al cliente. "
                    f"{p['linea']}: {p['salario']}"
                ),
            })
    return filas


def sugerencias(hechos):
    """Productos extra del catálogo 2026, solo con hechos explícitos. -> [(producto, razon)]"""
    edad = _edad(hechos)
    ciudad = _ciudad(hechos)
    civil = _civil(hechos)
    hijos = _tiene_hijos(hechos)
    banda = _banda(edad)
    salida = []

    def anotar(producto, razon):
        if (producto, razon) not in {(p, r) for p, r in salida}:
            salida.append((producto, razon))

    if hijos:
        extra = []
        if banda == "31-50" or (edad is not None and 31 <= edad <= 50):
            extra.append("la edad de compra más frecuente es 31-50")
        if ciudad in {"bogota", "medellin", "barranquilla", "cali", "bucaramanga"}:
            extra.append(f"{ciudad} es una de las sucursales con más pólizas educativas")
        detalle = ("; " + "; ".join(extra)) if extra else ""
        anotar("Seguro educativo",
               "Catálogo 2026: quienes compran educativo tienen un hijo de 0 a 12 años"
               + detalle + ".")

    if civil == "solter" and banda in {"", "21-30", "31-50"}:
        anotar("Seguro de vida",
               "Catálogo 2026: el 40% de quienes compran vida son solteros; edad típica 21-50.")
    elif ciudad == "medellin" and banda in {"", "21-30", "31-50"}:
        anotar("Seguro de vida",
               "Catálogo 2026: Medellín concentra el 38% de las pólizas de vida.")

    if edad is not None and edad >= 50:
        anotar("Seguro de pensión",
               "Catálogo 2026: pensiones se compran sobre todo entre 46 y 65 años.")
        anotar("Seguro renta vitalicia",
               "Catálogo 2026: rentas y Flex también se compran después de los 50.")
    elif banda == "31-50" and ciudad == "bogota" and not hijos:
        anotar("Seguro renta voluntaria",
               "Catálogo 2026: rentas y Flex se concentran entre 36 y 50 años, con el 65% en Bogotá.")
    return salida


def persistir():
    """Deja los perfiles 2026 en `conocimiento`, activos. Devuelve (nuevos, actualizados, iguales)."""
    filas = fragmentos()
    n = a = s = 0
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for f in filas:
                h = hashlib.sha256(f["contenido"].encode("utf-8")).hexdigest()
                cur.execute("""SELECT id_conocimiento, hash_contenido FROM public.conocimiento
                               WHERE LOWER(producto) = LOWER(%s) AND fuente_url = %s AND titulo = %s""",
                            (f["producto"], FUENTE, f["titulo"]))
                fila = cur.fetchone()
                if fila and fila[1] == h:
                    cur.execute("""UPDATE public.conocimiento SET activo = TRUE, categoria = %s,
                                   fecha_actualizacion = now() WHERE id_conocimiento = %s""",
                                (f["categoria"], fila[0]))
                    s += 1
                elif fila:
                    cur.execute("""UPDATE public.conocimiento SET contenido = %s, hash_contenido = %s,
                                   categoria = %s, activo = TRUE, fecha_actualizacion = now()
                                   WHERE id_conocimiento = %s""",
                                (f["contenido"], h, f["categoria"], fila[0]))
                    a += 1
                else:
                    cur.execute("""INSERT INTO public.conocimiento
                                   (categoria, producto, titulo, contenido, activo, fecha_actualizacion,
                                    fuente_url, hash_contenido)
                                   VALUES (%s,%s,%s,%s,TRUE,now(),%s,%s)""",
                                (f["categoria"], f["producto"], f["titulo"], f["contenido"], FUENTE, h))
                    n += 1
        conn.commit()
    finally:
        conn.close()
    print(f"Catálogo perfiles 2026: {n} nuevos, {a} actualizados, {s} sin cambios.")
    return n, a, s


if __name__ == "__main__":
    persistir()
