"""Hechos de vida a partir del markdown de un perfil público de red social.

Solo perfiles que la persona autorizó. Extrae lo que el texto dice de forma explícita
(trabajo actual, estudios, ubicación, familia). No infiere hijos, pareja ni ingresos.
"""
import re
import unicodedata
from urllib.parse import parse_qs, unquote, urlparse

HEAD = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
TELEFONO = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")

FAMILIA = re.compile(
    r"\b(soy madre|soy padre|madre de|padre de|mama de|papa de|mi hijo|mi hija|mis hijos|mis hijas|"
    r"tengo un hijo|tengo una hija|tengo hijos|esposo|esposa|mi pareja|casad[oa]|"
    r"mi hermano|mi hermana|mi madre|mi padre|mis padres|mi mama|mi papa)\b"
)
ESTUDIOS = re.compile(
    r"\b(estudie|estudio|estudiante|universidad|egresad|maestr|especializ|bachiller|colegio|"
    r"formacion|pregrado|posgrado|student|university|college)\b"
)
TRABAJO_VERBO = re.compile(
    r"\b(trabajo|trabaja|trabaje|empleo|cargo|experiencia laboral|actualmente)\b"
)
TRABAJO_CARGO = re.compile(
    r"\b(analista|gerente|coordinador|coordinadora|asesor|asesora|docente|abogad|desarrollador|"
    r"desarrolladora|contador|contadora|medic|enfermer|ingenier)\b"
)
UBICACION = re.compile(r"\b(vivo en|vive en|viviendo en|resido|ubicad|me mude|radicad)\b")
ESTADO_CIVIL = re.compile(
    r"\b(solter[oa]|casad[oa]|divorciad[oa]|viud[oa]|union libre|separad[oa]|"
    r"comprometid[oa]|en una relacion|me case|me divorcie)\b"
)
ESTADO_LABORAL = re.compile(
    r"\b(estoy desemplead[oa]|soy desemplead[oa]|quede desemplead[oa]|"
    r"estoy emplead[oa]|soy emplead[oa]|soy independiente|trabajo independiente|"
    r"soy autonom[oa]|estoy pensionad[oa]|soy pensionad[oa]|estoy jubilad[oa]|soy jubilad[oa]|"
    r"busco empleo|buscando empleo|soy freelancer|estoy en licencia|"
    r"actualmente trabajo|estoy trabajando)\b"
)
ESTADO_ACADEMICO = re.compile(
    r"\b(soy estudiante|estoy estudiando|estudio actualmente|estoy cursando|cursando|"
    r"soy egresad[oa]|soy graduad[oa]|me gradue|en semestre|semestre de)\b"
)
_VIAJE = re.compile(r"\b(vacacion|viaje|visitando|de paso|tour)\b")
_EDAD_AJENA = re.compile(r"\b(hij|niet|sobrin|espos|herman|padre|madre|mama|papa)\b")
CIUDAD = re.compile(
    r"^[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ .'-]{1,40},\s*[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ .'-]{1,40}$"
)
JUBILACION = re.compile(r"\b(jubil|pension)\b")
HIJOS = re.compile(r"\b(hijo|hija|hijos|hijas)\b")
PAREJA = re.compile(r"\b(esposo|esposa|pareja|casad[oa])\b")

DESCARTAR = (
    "seguidor", "follower", "following", "me gusta", "likes", "iniciar sesion", "sign in",
    "log in", "unete", "join now", "cookies", "contrasena", "password", "salario", "sueldo",
    "ingresos", "compensation", "salary", "mensaje directo", "enviar mensaje", "publicidad",
    "sponsored", "conectar", "connect",
)
MURO = (
    "inicia sesion para", "sign in to view", "join to view", "log in to see",
    "inicia sesion para ver", "join linkedin to see",
)
OMITIR_SECCION = (
    "aptitud", "skill", "recomendacion", "actividad", "publicacion", "comentario",
    "gente que", "personas que", "intereses", "licencia", "contacto",
)
MIN_CHARS = 12


def _n(texto):
    t = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _limpiar_linea(linea):
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", linea)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"[*_`>#]", "", t)
    t = EMAIL.sub("", t)
    t = TELEFONO.sub("", t)
    return re.sub(r"\s+", " ", t).strip(" -|·•\t")


def _descartar(texto):
    n = _n(texto)
    return (not n) or any(d in n for d in DESCARTAR) or bool(EMAIL.search(texto))


def clasificar_url(url):
    """-> (red, url_limpia) si es la página pública de un perfil. Si no, None."""
    raw = (url or "").strip()
    if not raw.lower().startswith("https://") or "REEMPLAZAR" in raw:
        return None
    partes_url = urlparse(raw)
    host = (partes_url.hostname or "").lower().removeprefix("www.")
    redes = {
        "linkedin.com": "linkedin",
        "instagram.com": "instagram",
        "facebook.com": "facebook",
        "fb.com": "facebook",
        "x.com": "x",
        "twitter.com": "x",
        "tiktok.com": "tiktok",
    }
    red = redes.get(host)
    if not red:
        return None
    partes = [unquote(s) for s in partes_url.path.split("/") if s]
    if not partes:
        return None
    bajas = [s.lower() for s in partes]
    if any(s in {"login", "signin", "signup", "messages", "messaging", "share", "search",
                 "settings", "explore", "intent"} for s in bajas):
        return None
    if red == "linkedin" and bajas[0] == "in" and len(partes) == 2:
        return red, f"https://www.linkedin.com/in/{partes[1]}"
    if red == "instagram" and len(partes) == 1 and bajas[0] not in {"p", "reel", "reels", "stories"}:
        return red, f"https://www.instagram.com/{partes[0]}/"
    if red == "facebook" and bajas[0] == "profile.php":
        ids = parse_qs(partes_url.query).get("id") or []
        if ids and ids[0].isdigit():
            return red, f"https://www.facebook.com/profile.php?id={ids[0]}"
        return None
    if red == "facebook" and len(partes) == 1 and bajas[0] not in {"watch", "groups", "events", "login", "profile.php"}:
        return red, f"https://www.facebook.com/{partes[0]}"
    if red == "x" and len(partes) == 1 and bajas[0] not in {"i", "home", "explore", "search"}:
        return red, f"https://x.com/{partes[0]}"
    if red == "tiktok" and len(partes) == 1 and partes[0].startswith("@"):
        return red, f"https://www.tiktok.com/{partes[0]}"
    return None


def cargar_autorizados(lista):
    """-> (personas, avisos). Cada persona trae solo URLs de perfil público y autorizado=true."""
    personas, avisos = [], []
    for item in lista or []:
        nombre = str((item or {}).get("nombre") or "").strip() or "sin nombre"
        if not isinstance(item, dict) or item.get("autorizado") is not True:
            avisos.append(f"{nombre}: se omite porque autorizado no está en true.")
            continue
        autorizacion = str(item.get("autorizacion") or "").strip()
        if len(autorizacion) < 15:
            avisos.append(f"{nombre}: se omite porque falta el texto de autorización.")
            continue
        if len(nombre) < 3 or nombre == "sin nombre":
            avisos.append("Se omite una entrada sin nombre.")
            continue
        urls = []
        for u in item.get("urls") or []:
            clasificada = clasificar_url(str(u))
            if not clasificada:
                avisos.append(f"{nombre}: URL no usable como perfil público ({u}).")
            else:
                red, limpia = clasificada
                urls.append({"red": red, "url": limpia})
        if not urls:
            avisos.append(f"{nombre}: no quedó ningún perfil público utilizable.")
            continue
        personas.append({
            "nombre": nombre,
            "clave_cliente": str(item.get("clave_cliente") or "").strip() or None,
            "autorizacion": autorizacion,
            "urls": urls,
        })
    return personas, avisos


def es_muro_de_acceso(markdown):
    n = _n(markdown or "")
    return any(m in n for m in MURO) and len(n) < 900


def _tipo_seccion(titulo):
    n = _n(titulo)
    if any(k in n for k in OMITIR_SECCION):
        return "omitir"
    if any(k in n for k in ("experiencia", "experience", "empleo", "trabajo")):
        return "Trabajo"
    if any(k in n for k in ("educacion", "education", "estudios", "formacion")):
        return "Estudios"
    if "familia" in n or "family" in n:
        return "Familia"
    if any(k in n for k in ("ubicacion", "location")):
        return "Ubicacion"
    if any(k in n for k in ("acerca", "about", "biografia", "resumen")):
        return "Situacion actual"
    return None


def _oraciones(texto):
    partes = re.split(r"\n+|(?<=[.!?])\s+", texto)
    vistas, salida = set(), []
    for p in partes:
        p = p.strip(" .")
        clave = _n(p)
        if clave and clave not in vistas:
            vistas.add(clave)
            salida.append(p)
    return salida


def categorias_oracion(texto, seccion=None):
    if _descartar(texto) or len(texto) < MIN_CHARS:
        return []
    n = _n(texto)
    cats = []
    if FAMILIA.search(n):
        cats.append("Familia")
    if _EDAD_TEXTO.search(n) or (re.search(r"\bnaci\b", n) and re.search(r"\b(19|20)\d{2}\b", n)):
        if not _EDAD_AJENA.search(n):
            cats.append("Edad")
    if ESTADO_CIVIL.search(n):
        cats.append("Estado civil")
    if seccion == "Estudios" or ESTUDIOS.search(n):
        cats.append("Estudios")
    if ESTADO_ACADEMICO.search(n):
        cats.append("Estado academico")
    trabajo = seccion == "Trabajo" or bool(TRABAJO_VERBO.search(n))
    if not trabajo and TRABAJO_CARGO.search(n) and "Estudios" not in cats:
        trabajo = True
    if trabajo:
        cats.append("Trabajo")
    if ESTADO_LABORAL.search(n) or re.fullmatch(
            r"(autonom[oa]|independiente|emplead[oa]|desemplead[oa]|pensionad[oa]|jubilad[oa]|estudiante)", n):
        cats.append("Estado laboral" if not re.fullmatch(r"estudiante", n) else "Estado academico")
    if (seccion == "Ubicacion" or UBICACION.search(n) or CIUDAD.match(texto)) and not _VIAJE.search(n):
        cats.append("Ubicacion")
    if seccion == "Situacion actual" and not cats and len(texto) >= 40:
        cats.append("Situacion actual")
    return list(dict.fromkeys(cats))


def _bloques(markdown):
    bloques, seccion, buf = [], "Situacion actual", []

    def cerrar():
        if buf and seccion != "omitir":
            bloques.append((seccion, list(buf)))
        buf.clear()

    vio_h1 = False
    for linea in (markdown or "").splitlines():
        m = HEAD.match(linea)
        if m and len(m.group(1)) <= 3:
            cerrar()
            if len(m.group(1)) == 1 and not vio_h1:
                vio_h1 = True
                seccion = "Situacion actual"
                continue
            tipo = _tipo_seccion(_limpiar_linea(m.group(2)))
            if tipo:
                seccion = tipo
            continue
        buf.append(linea)
    cerrar()
    return bloques


_CAMPOS_FRASE = {
    "Familia": "familia",
    "Edad": "edad",
    "Trabajo": "experiencia",
    "Estudios": "educacion",
    "Ubicacion": "ubicacion",
    "Estado civil": "estado_civil",
    "Estado laboral": "estado_laboral",
    "Estado academico": "estado_academico",
}


def _anexar_campo(info, campo, frase):
    actual = info.get(campo) or ""
    if _n(frase) and _n(frase) not in _n(actual):
        info[campo] = ". ".join(p for p in (actual, frase) if p)


def edad_de_frase(frase, hoy=None):
    """Edad dicha por la persona, o calculada si escribió su año de nacimiento."""
    from datetime import date
    n = _n(frase)
    if not n or _EDAD_AJENA.search(n):
        return ""
    hallado = _EDAD_TEXTO.search(n)
    if hallado:
        edad = int(hallado.group(1))
        return f"{edad} años" if 15 <= edad <= 100 else ""
    if re.search(r"\bnaci\b", n):
        anio = re.search(r"\b(19|20)\d{2}\b", n)
        if anio:
            edad = (hoy or date.today()).year - int(anio.group(0))
            if 15 <= edad <= 100:
                return f"{edad} años"
    return ""


def aplicar_frase(info, frase, hoy=None):
    """Suma a la ficha lo que una frase propia dice de edad, estado civil, lugar, trabajo o estudios."""
    frase = quitar_fechas_iso(re.sub(r"\s+", " ", frase or "").strip(" ."))
    if len(frase) < 8 or _descartar(frase):
        return info
    edad = edad_de_frase(frase, hoy)
    if edad:
        texto = frase if _EDAD_TEXTO.search(_n(frase)) else f"{edad} ({frase})"
        _anexar_campo(info, "edad", texto)
    for cat in categorias_oracion(frase):
        campo = _CAMPOS_FRASE.get(cat)
        if campo and campo != "edad":
            _anexar_campo(info, campo, frase)
    return info


def aplicar_lo_publicado(info, posts, hoy=None):
    """Lee publicaciones propias (no reposts ni comentarios) y completa la ficha."""
    info = dict(info or {})
    for post in posts or []:
        if (post.get("tipo") or "publicacion") == "compartida":
            continue
        for oracion in _oraciones(post.get("texto") or ""):
            aplicar_frase(info, oracion, hoy)
    return info


def hechos_de_perfil(markdown):
    """-> [{categoria, titulo, contenido}] solo con frases explícitas del perfil."""
    if es_muro_de_acceso(markdown):
        return []
    crudos = []
    for seccion, lineas in _bloques(markdown):
        limpias = [_limpiar_linea(l) for l in lineas]
        texto = "\n".join(t for t in limpias if t)
        for oracion in _oraciones(texto):
            oracion = quitar_fechas_iso(oracion)
            for cat in categorias_oracion(oracion, seccion):
                crudos.append((cat, oracion[:400]))
    vistos, cuenta, salida = set(), {}, []
    for cat, contenido in crudos:
        clave = (cat, _n(contenido))
        if clave in vistos:
            continue
        vistos.add(clave)
        n = cuenta.get(cat, 0) + 1
        cuenta[cat] = n
        titulo = cat if n == 1 else f"{cat} ({n})"
        salida.append({"categoria": cat, "titulo": titulo, "contenido": contenido})
    return salida


_CLAVES_OMITIDAS = {
    "id", "email", "emails", "phone", "phones", "skill", "skills", "publicemail",
    "profilepictureurl", "followerscount", "followingcount", "postscount", "likescount",
    "latitude", "longitude", "locationlatitude", "locationlongitude", "platformid",
    "locationplatformid", "biolink", "createdat", "updatedat", "isverified", "isprivate",
    "linkedinurl", "profileurl", "handle", "language", "languages",
}


def _clave(texto):
    return _n(texto).replace("_", "").replace("-", "")


def _saltar_clave(clave):
    n = _clave(clave)
    return n in _CLAVES_OMITIDAS or n.endswith("url") or "email" in n or "phone" in n


def _primera_persona(data):
    if isinstance(data, list):
        return data[0] if data and isinstance(data[0], dict) else None
    if not isinstance(data, dict):
        return None
    for clave in ("people", "results", "matches"):
        valor = data.get(clave)
        if isinstance(valor, list):
            personas = [item for item in valor if isinstance(item, dict)]
            return personas[0] if personas else None
    persona = data.get("person")
    if isinstance(persona, dict):
        return persona
    data_anidada = data.get("data")
    if isinstance(data_anidada, list):
        return data_anidada[0] if data_anidada and isinstance(data_anidada[0], dict) else None
    if isinstance(data_anidada, dict):
        return data_anidada
    if any(k in data for k in ("bio", "headline", "employment", "full_name", "handle", "displayName")):
        return data
    return None


def ficha_vacia(data):
    if isinstance(data, list):
        return not data
    if not isinstance(data, dict):
        return True
    for clave in ("people", "results", "data", "matches"):
        if clave in data and isinstance(data[clave], list):
            return not any(isinstance(item, dict) for item in data[clave])
    return _primera_persona(data) is None


def es_perfil_privado(data):
    persona = _primera_persona(data) or {}
    pila = [persona]
    while pila:
        actual = pila.pop()
        if not isinstance(actual, dict):
            continue
        for clave, valor in actual.items():
            if _clave(clave) in {"isprivate", "private"} and valor is True:
                return True
            if isinstance(valor, dict):
                pila.append(valor)
    return False


def _cubeta(ruta):
    n = " ".join(_clave(p) for p in ruta)
    if any(k in n for k in ("employ", "experience", "job", "position", "company", "organization")):
        return "Trabajo"
    if any(k in n for k in ("educat", "school", "degree", "fieldofstudy")):
        return "Estudios"
    if any(k in n for k in ("location", "city", "region", "country", "address")):
        return "Ubicacion"
    if ruta and _clave(ruta[-1]) == "title":
        return "Situacion actual"
    if any(k in n for k in ("bio", "description", "about", "summary", "headline")):
        return "Situacion actual"
    return None


def _volcar(obj, ruta, cubetas):
    if isinstance(obj, dict):
        if ruta and _cubeta(ruta[-1:]) == "Ubicacion":
            partes = [v.strip() for k, v in obj.items()
                      if isinstance(v, str) and v.strip() and not _saltar_clave(k)]
            if partes:
                cubetas["Ubicacion"].append(", ".join(partes))
            return
        for clave, valor in obj.items():
            if _saltar_clave(clave) or _clave(clave) in {"matchconfidence", "emailstatus"}:
                continue
            if _clave(clave) == "organization" and isinstance(valor, dict):
                nombre_empresa = valor.get("name")
                if isinstance(nombre_empresa, str):
                    _volcar(nombre_empresa, ruta + [clave, "name"], cubetas)
                continue
            if _clave(clave) == "employmenthistory" and isinstance(valor, list):
                for puesto in valor:
                    if not isinstance(puesto, dict):
                        continue
                    for sub in ("title", "organization_name", "company_name"):
                        texto_puesto = puesto.get(sub)
                        if isinstance(texto_puesto, str):
                            _volcar(texto_puesto, ruta + ["employment", sub], cubetas)
                continue
            _volcar(valor, ruta + [clave], cubetas)
        return
    if isinstance(obj, list):
        for item in obj:
            _volcar(item, ruta, cubetas)
        return
    if not isinstance(obj, str):
        return
    texto = obj.strip()
    if not texto or EMAIL.search(texto) or texto.lower().startswith("http"):
        return
    destino = _cubeta(ruta)
    if destino:
        cubetas[destino].append(texto)


def markdown_desde_ficha(data):
    """Pasa una ficha estructurada al markdown que ya entiende `hechos_de_perfil`."""
    persona = _primera_persona(data)
    if not persona or es_perfil_privado(data):
        return ""
    cubetas = {"Situacion actual": [], "Trabajo": [], "Estudios": [], "Ubicacion": []}
    _volcar(persona, [], cubetas)
    nombre = ""
    for clave in ("full_name", "name", "displayName", "display_name"):
        valor = persona.get(clave)
        if isinstance(valor, str) and valor.strip():
            nombre = valor.strip()
            break
    lineas = [f"# {nombre or 'Perfil'}", ""]
    for titulo, cubeta in (("Situacion actual", None), ("Ubicacion", "Ubicacion"),
                           ("Experiencia", "Trabajo"), ("Educacion", "Estudios")):
        textos = list(dict.fromkeys(cubetas["Situacion actual" if cubeta is None else cubeta]))
        if not textos:
            continue
        if cubeta is not None:
            lineas += [f"## {titulo}", ""]
        lineas += textos
        lineas.append("")
    return "\n".join(lineas).strip()


def normalizar_correo(texto):
    hallado = EMAIL.search(str(texto or ""))
    if not hallado:
        return None
    correo = hallado.group(0).lower()
    if "email_not_unlocked" in correo or correo.endswith("@domain.com"):
        return None
    return correo


def normalizar_celular(texto):
    digitos = re.sub(r"\D", "", str(texto or ""))
    if digitos.startswith("57") and len(digitos) == 12:
        digitos = digitos[2:]
    if 10 <= len(digitos) <= 15:
        return digitos
    return None


def _tipo_contacto(clave):
    n = _clave(clave)
    if "status" in n:
        return None
    if n in {"email", "emails", "publicemail", "correo"} or n.endswith("email"):
        return "Correo"
    if n in {"phone", "phones", "celular", "mobile", "telefono"} or n.endswith("phone"):
        return "Celular"
    return None


def _juntar_contactos(pares):
    vistos, salida = set(), []
    for titulo, contenido in pares:
        if (titulo, contenido) in vistos:
            continue
        vistos.add((titulo, contenido))
        salida.append({"categoria": "Contacto", "titulo": titulo, "contenido": contenido})
    return salida


def contactos_de_texto(markdown):
    """Correo y celular escritos en el perfil. No entran al texto de vida."""
    if es_muro_de_acceso(markdown):
        return []
    pares = []
    for correo in EMAIL.findall(markdown or ""):
        limpio = normalizar_correo(correo)
        if limpio:
            pares.append(("Correo", limpio))
    for telefono in TELEFONO.findall(markdown or ""):
        limpio = normalizar_celular(telefono)
        if limpio:
            pares.append(("Celular", limpio))
    return _juntar_contactos(pares)


def contactos_de_ficha(data):
    """Contacto de la persona. El teléfono de la empresa no cuenta."""
    persona = _primera_persona(data)
    if not persona or es_perfil_privado(data):
        return []
    pares = []

    def recorrer(obj, ruta):
        if any(_clave(parte) == "organization" for parte in ruta):
            return
        if isinstance(obj, dict):
            for clave, valor in obj.items():
                tipo = _tipo_contacto(clave)
                if tipo and isinstance(valor, str):
                    limpio = normalizar_correo(valor) if tipo == "Correo" else normalizar_celular(valor)
                    if limpio:
                        pares.append((tipo, limpio))
                elif isinstance(valor, (dict, list)):
                    recorrer(valor, ruta + [clave])
        elif isinstance(obj, list):
            for item in obj:
                recorrer(item, ruta)

    recorrer(persona, [])
    return _juntar_contactos(pares)


_IDENTIFICADOR = re.compile(r"^[a-f0-9]{16,}$", re.I)
_EDAD_TEXTO = re.compile(r"\b(\d{1,2})\s+anos\b")
# Fechas de sistema: 2022-08-01, 2022-08-01T00:00:00Z o (2026-09-01 - None). No aportan.
# Un año suelto, como "2022 - actualidad", sí se conserva.
_FECHA_MAQUINA = r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?"
_VACIO = r"(?:\b(?:none|null|undefined|n/?a)\b|\?)"
_EXTREMO = rf"(?:{_FECHA_MAQUINA}|{_VACIO}|actualidad|presente|present|current)"
_RANGO_BASURA = re.compile(
    rf"(?:\(\s*)?(?:{_FECHA_MAQUINA}|{_VACIO})\s*[-–—]\s*{_EXTREMO}(?:\s*\))?"
    rf"|(?:\(\s*)?{_EXTREMO}\s*[-–—]\s*(?:{_FECHA_MAQUINA}|{_VACIO})(?:\s*\))?",
    re.I,
)
_FECHA_SUELTA = re.compile(rf"(?:\(\s*)?{_FECHA_MAQUINA}(?:\s*\))?", re.I)
# Lo que queda si una limpieza anterior se llevó la fecha y dejó " - None)".
_RESTO_VACIO = re.compile(
    rf"(?:\(\s*)?[-–—]\s*{_VACIO}\s*\)?|\(\s*{_VACIO}\s*\)",
    re.I,
)
_ANIO = re.compile(r"^\d{4}$")
_AHORA = {"actualidad", "presente", "present", "current", "hoy"}
_NO_FECHA = {"none", "null", "undefined", "n/a", "na", "?", "-", "—", "–"}


def quitar_fechas_iso(texto):
    """Saca fechas de sistema y rangos vacíos, como (2026-09-01 - None)."""
    if not texto:
        return texto
    t = _RANGO_BASURA.sub(" ", str(texto))
    t = _FECHA_SUELTA.sub(" ", t)
    t = _RESTO_VACIO.sub(" ", t)
    t = re.sub(r"\(\s*\)", " ", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip(" -·\t")


def _texto_util(valor):
    if valor is None or isinstance(valor, (bool, int, float)):
        if isinstance(valor, int) and not isinstance(valor, bool):
            return str(valor)
        return None
    if not isinstance(valor, str):
        return None
    texto = valor.strip()
    if not texto or _IDENTIFICADOR.match(texto) or texto.lower().startswith("http"):
        return None
    return texto


def _agregar(hechos, categoria, contenido):
    contenido = quitar_fechas_iso(contenido)
    contenido = re.sub(r"\s+", " ", (contenido or "")).strip(" -")
    if len(contenido) < 3:
        return
    if any(h["categoria"] == categoria and _n(h["contenido"]) == _n(contenido) for h in hechos):
        return
    hechos.append({"categoria": categoria, "titulo": categoria, "contenido": contenido[:400]})


def _frases_personales(hechos, texto):
    for oracion in _oraciones(texto or ""):
        n = _n(oracion)
        if FAMILIA.search(n) or PAREJA.search(n) or HIJOS.search(n):
            _agregar(hechos, "Familia", oracion)
        edad = _EDAD_TEXTO.search(n)
        if edad:
            _agregar(hechos, "Edad", f"{edad.group(1)} años")


def _fecha_legible(valor):
    """Solo un año o 'actualidad'. Una fecha de sistema o None no se muestra."""
    if valor in (None, ""):
        return None
    texto = (_texto_util(str(valor)) or "").strip()
    if not texto or texto.lower() in _NO_FECHA:
        return None
    if _ANIO.fullmatch(texto):
        return texto
    if texto.lower() in _AHORA:
        return "actualidad"
    return None


def _linea_puesto(puesto):
    cargo = _texto_util(puesto.get("title"))
    empresa = _texto_util(puesto.get("organization_name") or puesto.get("company_name") or puesto.get("company"))
    if isinstance(empresa, str) and _IDENTIFICADOR.match(empresa):
        empresa = None
    inicio = _fecha_legible(puesto.get("start_date") or puesto.get("start_at") or puesto.get("started_at"))
    fin = _fecha_legible(puesto.get("end_date") or puesto.get("end_at") or puesto.get("ended_at"))
    linea = " en ".join(parte for parte in (cargo, empresa) if parte)
    if linea and (inicio or fin):
        linea += f" ({inicio or '?'} - {fin or 'actualidad'})"
    return linea


def _linea_estudio(edu):
    if isinstance(edu, str):
        return _texto_util(edu)
    if not isinstance(edu, dict):
        return None
    grado = _texto_util(edu.get("degree") or edu.get("diploma"))
    area = _texto_util(edu.get("major") or edu.get("field_of_study") or edu.get("field"))
    escuela = _texto_util(edu.get("school_name") or edu.get("school") or edu.get("name")
                          or edu.get("organization_name"))
    return ", ".join(parte for parte in (grado, area, escuela) if parte) or None


def hechos_desde_ficha(data):
    """Todos los datos personales que la ficha trae llenos. Omite identificadores y datos de la empresa."""
    persona = _primera_persona(data)
    if not persona or es_perfil_privado(data):
        return []
    hechos = []
    direccion = _texto_util(persona.get("formatted_address"))
    if direccion:
        _agregar(hechos, "Ubicacion", direccion)
    else:
        partes = [_texto_util(persona.get(clave)) for clave in ("city", "state", "country")]
        if any(partes):
            _agregar(hechos, "Ubicacion", ", ".join(parte for parte in partes if parte))

    titular = _texto_util(persona.get("headline")) or _texto_util(persona.get("title"))
    if titular:
        _agregar(hechos, "Situacion actual", titular)
    resumen = _texto_util(persona.get("summary") or persona.get("about") or persona.get("description")
                          or persona.get("bio"))
    if resumen and (not titular or _n(resumen) != _n(titular)):
        _agregar(hechos, "Situacion actual", resumen)

    historial = []
    crudo = persona.get("employment_history")
    if isinstance(crudo, list):
        historial.extend(item for item in crudo if isinstance(item, dict))
    empleo = persona.get("employment")
    if isinstance(empleo, dict):
        for valor in empleo.values():
            if isinstance(valor, dict):
                historial.append(valor)
            elif isinstance(valor, list):
                historial.extend(item for item in valor if isinstance(item, dict))
    elif isinstance(empleo, list):
        historial.extend(item for item in empleo if isinstance(item, dict))
    for puesto in historial:
        linea = _linea_puesto(puesto)
        if linea:
            _agregar(hechos, "Trabajo", linea)
        estudio = _linea_estudio({"degree": puesto.get("degree"), "major": puesto.get("major"),
                                  "school_name": puesto.get("school_name")})
        if estudio:
            _agregar(hechos, "Estudios", estudio)
        _frases_personales(hechos, puesto.get("description") or "")

    estudios = []
    for clave in ("educations", "education", "schools"):
        bloque = persona.get(clave)
        if isinstance(bloque, dict):
            estudios.append(bloque)
        elif isinstance(bloque, list):
            estudios.extend(bloque)
    for edu in estudios:
        linea = _linea_estudio(edu)
        if linea:
            _agregar(hechos, "Estudios", linea)

    if isinstance(persona.get("age"), int) and 15 <= persona["age"] <= 100:
        _agregar(hechos, "Edad", f"{persona['age']} años")
    nacimiento = persona.get("birth_date") or persona.get("birth_year") or persona.get("birthday")
    if nacimiento not in (None, ""):
        _agregar(hechos, "Edad", f"Nacimiento: {nacimiento}")
    civil = _texto_util(persona.get("marital_status") or persona.get("estado_civil"))
    if civil:
        _agregar(hechos, "Familia", civil)

    _frases_personales(hechos, "\n".join(filter(None, [titular, resumen])))

    cuenta, salida = {}, []
    for hecho in hechos:
        n = cuenta.get(hecho["categoria"], 0) + 1
        cuenta[hecho["categoria"]] = n
        titulo = hecho["categoria"] if n == 1 else f"{hecho['categoria']} ({n})"
        salida.append({**hecho, "titulo": titulo})
    return salida


def ciudad_usable(texto):
    """Se queda con la ciudad y deja fuera el país o el código de país."""
    partes = [p.strip() for p in str(texto or "").split(",") if p.strip()]
    partes = [p for p in partes if _n(p) not in {"co", "colombia"} and len(p) > 2]
    return partes[0] if partes else (str(texto or "").strip() or None)


def datos_para_cliente(hechos):
    """Campos de clientes que sí están dichos en los hechos. Sin salario."""
    def primero(categoria):
        for h in hechos:
            if h["categoria"] == categoria and h.get("contenido"):
                return h["contenido"]
        return None

    def contacto(titulo):
        for h in hechos:
            if h["categoria"] == "Contacto" and str(h.get("titulo") or "").startswith(titulo):
                return h["contenido"]
        return None

    situacion = primero("Situacion actual") or ""
    profesion = primero("Trabajo")
    if not profesion and re.search(r"\b(student|estudiante)\b", _n(situacion)):
        profesion = "Estudiante"
    producto = next((h["titulo"] for h in hechos if h["categoria"] == "Producto sugerido" and h.get("titulo")), None)
    return {
        "producto_interes": producto,
        "universidad": primero("Estudios"),
        "ciudad": ciudad_usable(primero("Ubicacion")),
        "profesion": profesion,
        "correo": contacto("Correo"),
        "celular": contacto("Celular"),
    }


def sugerir_productos(hechos):
    """Producto de Global que encaja con un hecho explícito. La persona revisa antes de usarlo."""
    por_producto = {}
    for h in hechos:
        if h["categoria"] == "Producto sugerido" or _IDENTIFICADOR.match(h["contenido"].strip()):
            continue
        n = _n(h["contenido"])
        razones = por_producto
        candidatos = []
        if h["categoria"] == "Estudios" or ESTUDIOS.search(n):
            candidatos.append("Seguro educativo")
        if h["categoria"] == "Familia" and HIJOS.search(n):
            candidatos += ["Seguro educativo", "Seguro de vida"]
        if h["categoria"] in ("Familia", "Estado civil") and PAREJA.search(n):
            candidatos.append("Seguro de vida")
        if h["categoria"] == "Trabajo":
            candidatos += ["Seguro de vida", "Seguro de accidentes personales"]
        if JUBILACION.search(n):
            candidatos += ["Seguro de pensión", "Seguro renta vitalicia"]
        porque = f"{h['categoria']}: {h['contenido']}"
        for producto in candidatos:
            razones.setdefault(producto, [])
            if porque not in razones[producto]:
                razones[producto].append(porque)
    return [{"categoria": "Producto sugerido", "titulo": producto,
             "contenido": " | ".join(razones)} for producto, razones in por_producto.items()]
