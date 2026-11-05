"""Gustos de vida a partir de páginas seguidas, reposts y publicaciones.

No infiere política ni religión. Cada categoría que sí encaja queda como hecho
«Gusto» (con cómo acercarse y, si aplica, un producto del catálogo).
"""
import re
import unicodedata
from collections import defaultdict

# categoria -> (patrones ya sin tildes, texto de acercamiento, producto o None)
_REGLAS = (
    ("Finanzas",
     r"finanza|banco|bancolombia|davivienda|bancol|nubank|nu bank|bbva|colpatria|"
     r"inversion|inversor|bolsa de valores|crypto|cripto|bitcoin|ahorro|economia|"
     r"economista|dinero|presupuesto|impuesto|tribut|fondo de inversion|etf|"
     r"broker|trader|trading|fintech|seguros? global|portafolio",
     "Hablar de ahorro, inversión y de proteger el patrimonio.",
     "Seguro renta voluntaria"),
    ("Nutricion",
     r"nutricion|nutriologo|dieta|saludable|alimentacion|vegano|vegetariano|"
     r"calorias|proteina|receta saludable|comida sana|superfood|organico",
     "Hablar de hábitos de alimentación y bienestar.",
     "Seguro de vida"),
    ("Deportes",
     r"deporte|deportivo|futbol|ciclismo|cicla|bici|running|correr|"
     r"maraton|gimnasio|gym\b|crossfit|yoga|pilates|nba|fifa|uefa|olimpic|"
     r"natacion|tenis|golf|boxeo|mma\b|ufc\b|atletismo|triathlon|spinning|"
     r"federacion.*cicl|liga de|hincha|equipo de",
     "Hablar de actividad física y de prevenir lesiones o accidentes.",
     "Seguro de accidentes personales"),
    ("Moda",
     r"\bmoda\b|fashion|outfit|styling|zapatos|calzado|ropa\b|vestuario|"
     r"\bzara\b|shein|gucci|prada|balenciaga|h&m\b|bershka|pull.?and.?bear|"
     r"tendencia de moda|diseñador de moda",
     "Usar un tono cercano a estilo y tendencias, sin forzar un producto.",
     None),
    ("Entretenimiento",
     r"netflix|disney|hbo|prime video|cine\b|pelicula|series?\b|podcast|"
     r"standup|humor|comedia|meme|tiktok|influencer|espectaculo|concierto|"
     r"festival de|entretenimiento",
     "Partir de lo que ve o sigue (series, cine, creadores) para abrir la conversación.",
     None),
    ("Musica",
     r"\bmusica\b|spotify|apple music|cantante|banda de|reggaeton|rock\b|"
     r"salsa\b|vallenato|dj\b|album\b|lyric",
     "Abrir con lo que escucha o los artistas que sigue.",
     None),
    ("Tecnologia",
     r"tecnolog|tech\b|gadget|smartphone|iphone|android|inteligencia artificial|"
     r"\bia\b|software|programacion|developer|start.?up|silicon|apple\b|"
     r"google\b|microsoft|openai",
     "Hablar de herramientas, trabajo digital o protección de lo que construye.",
     "Seguro de vida"),
    ("Viajes",
     r"viaje|viajero|travel|turismo|vacacion|aerolinea|avion|hoteles?|"
     r"booking|airbnb|mochilero|destino|playa\b|resort",
     "Hablar de desplazarse y viajar con un respaldo si algo sale mal.",
     "Seguro de accidentes personales"),
    ("Educacion",
     r"universidad|universitario|eafit|andes\b|javeriana|nacional de colombia|"
     r"colegio|educacion|maestria|posgrado|pregrado|estudiante|academic|"
     r"curso online|platzi|coursera|edx\b",
     "Hablar de estudios y de cómo financiar o proteger ese proyecto.",
     "Seguro educativo"),
    ("Familia",
     r"maternidad|paternidad|crianza|parenting|bebes?|hijos|familia|"
     r"mama de|papa de",
     "Hablar del cuidado de quienes dependen de la persona.",
     "Seguro de vida"),
    ("Salud",
     r"\bsalud\b|medico|medicina|clinica|hospital|bienestar|wellness|"
     r"salud mental|psicolog|terapia|odontolog",
     "Hablar de prevención y de cuidar la salud a largo plazo.",
     "Seguro de vida"),
    ("Motor",
     r"\bmoto\b|motocicleta|automovil|automotriz|carro\b|coches?|toyota|"
     r"mazda|chevrolet|renault|kawasaki|yamaha|ducati|formula.?1|f1\b|"
     r"tuning|concesionario",
     "Hablar de movilidad y de lo que implica estar en la vía.",
     "Seguro de accidentes personales"),
    ("Mascotas",
     r"mascota|perro|gato|veterinari|pet\b|dog\b|cat\b|animal de compañia",
     "Hablar del cuidado de sus animales. El catálogo actual no tiene producto de mascotas.",
     None),
    ("Belleza",
     r"belleza|maquillaje|skincare|cosmet|estetica|peluquer|barber",
     "Tono cercano a cuidado personal e imagen.",
     None),
    ("Gastronomia",
     r"gastronom|restaurante|chef\b|cocina|foodie|cafeteria|bar de|"
     r"comida\b|recetas?",
     "Partir de lo que come o de los sitios que sigue para abrir la conversación.",
     None),
    ("Cultura",
     r"museo|teatro|literatura|poesia|libro\b|lectura|editorial|"
     r"arte contemporaneo|galeria",
     "Abrir con lo que lee, ve o visita.",
     None),
    ("Noticias",
     r"noticias|periodico|diario\b|el tiempo|el espectador|semana\b|"
     r"bloomberg|cnn\b|bbc\b|reuters|la fm|caracol|rcn\b|revista",
     "La persona se informa con medios; ir al grano y con datos.",
     None),
    ("Emprendimiento",
     r"emprend|emprendedor|negocio propio|pyme|startup|founders?|"
     r"empresari",
     "Hablar de proteger el negocio y a quien lo saca adelante.",
     "Seguro de vida"),
    ("Inmuebles",
     r"inmueble|inmobiliari|vivienda|apartamento|finca raiz|bienes raices|"
     r"arrendamiento|hipoteca",
     "Hablar de proteger el patrimonio y el techo.",
     "Seguro de vida"),
    ("Gaming",
     r"\bgaming\b|\bgamer\b|videojuegos|playstation|xbox\b|nintendo|"
     r"esport|twitch|steam\b",
     "Partir de lo que juega o sigue en streaming.",
     None),
    ("Medio ambiente",
     r"medio ambiente|sostenib|ecolog|cambio climatico|recicl|ambiental|"
     r"energia renovable",
     "Hablar de cuidado a largo plazo, alineado con lo que valora.",
     None),
)

_COMPILADAS = tuple(
    (nombre, re.compile(patron), acercamiento, producto)
    for nombre, patron, acercamiento, producto in _REGLAS
)


def _n(texto):
    t = unicodedata.normalize("NFD", str(texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


def clasificar(texto):
    """Categorías de gusto que encajan con un nombre de página o un texto."""
    n = _n(texto)
    if len(n) < 3:
        return []
    return [nombre for nombre, patron, *_ in _COMPILADAS if patron.search(n)]


def categoria_desde_titulo(titulo):
    t = str(titulo or "").strip()
    prefijo = "Gusto · "
    return t[len(prefijo):] if t.startswith(prefijo) else t


def producto_de_gusto(categoria):
    categoria = categoria_desde_titulo(categoria)
    for nombre, _patron, _acercamiento, producto in _COMPILADAS:
        if nombre == categoria:
            return producto
    return None


def acercamiento_de_gusto(categoria):
    for nombre, _patron, acercamiento, _producto in _COMPILADAS:
        if nombre == categoria:
            return acercamiento
    return ""


def senales(info, posts=None):
    """categoria -> {sigue, interactua, publicaciones}."""
    from app.redes_seguidas import lista_nombres

    info = info or {}
    hallado = defaultdict(lambda: {"sigue": [], "interactua": [], "publicaciones": 0})

    def anotar(categoria, campo, valor):
        cubeta = hallado[categoria]
        if valor and valor not in cubeta[campo]:
            cubeta[campo].append(valor)

    for nombre in lista_nombres(info.get("sigue_a")):
        for cat in clasificar(nombre):
            anotar(cat, "sigue", nombre)
    for nombre, _n_veces in info.get("reposts") or []:
        for cat in clasificar(nombre):
            anotar(cat, "interactua", nombre)
    for post in posts or []:
        texto = " ".join(filter(None, [
            post.get("autor") or "",
            post.get("texto") or "",
            post.get("contexto_social") or "",
        ]))
        cats = clasificar(texto)
        autor = (post.get("autor") or "").strip()
        for cat in cats:
            hallado[cat]["publicaciones"] += 1
            if autor:
                anotar(cat, "interactua", autor)
    return {k: v for k, v in hallado.items() if v["sigue"] or v["interactua"] or v["publicaciones"]}


def hechos_de_gustos(info, posts=None):
    """Un hecho Gusto por categoría, con cómo acercarse y el producto afín si existe."""
    dueno = (info or {}).get("nombre") or "Esta persona"
    hechos = []
    for categoria, datos in senales(info, posts).items():
        partes = []
        if datos["sigue"]:
            partes.append("Sigue: " + ", ".join(datos["sigue"][:8]))
        if datos["interactua"]:
            partes.append("Interactúa con: " + ", ".join(datos["interactua"][:8]))
        if datos["publicaciones"]:
            n = datos["publicaciones"]
            partes.append(f"{n} publicación(es) de este tema")
        acercamiento = acercamiento_de_gusto(categoria)
        if acercamiento:
            partes.append("Cómo acercarse: " + acercamiento)
        producto = producto_de_gusto(categoria)
        if producto:
            partes.append("Producto afín: " + producto)
        hechos.append({
            "categoria": "Gusto",
            "titulo": f"Gusto · {categoria}",
            "contenido": f"{dueno}. " + ". ".join(partes) + ".",
        })
    hechos.sort(key=lambda h: h["titulo"])
    return hechos
