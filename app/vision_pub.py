"""Lee el texto de las fotos de un post y arma un resumen de lo que contienen.

Sirve para gustos e intereses: infografías, citas, capturas y recortes con letra.
No falla el scrape si OCR no está instalado.
"""
import re

_motor = None
_sin_ocr = False


def _acotar(texto, n=140):
    t = re.sub(r"\s+", " ", str(texto or "")).strip()
    if len(t) <= n:
        return t
    corte = t[:n].rsplit(" ", 1)[0].strip()
    return (corte or t[:n]).rstrip(".,;:") + "…"


def _rapid():
    global _motor, _sin_ocr
    if _sin_ocr:
        return None
    if _motor is not None:
        return _motor
    try:
        from rapidocr_onnxruntime import RapidOCR
        _motor = RapidOCR()
        return _motor
    except Exception as e:
        print(f"OCR de imágenes no disponible: {e}")
        _sin_ocr = True
        return None


def leer_texto(ruta_png):
    """Texto visible dentro de un PNG. Vacío si no hay letra o no hay motor."""
    if not ruta_png:
        return ""
    path = str(ruta_png)
    motor = _rapid()
    if motor is not None:
        try:
            result, _elapse = motor(path)
            piezas = []
            for item in result or []:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    t = re.sub(r"\s+", " ", str(item[1] or "")).strip()
                    if len(t) >= 2:
                        piezas.append(t)
            if piezas:
                return " ".join(piezas)[:800]
        except Exception as e:
            print(f"OCR RapidOCR falló: {e}")
    try:
        import pytesseract
        from PIL import Image
        t = pytesseract.image_to_string(Image.open(path), lang="spa+eng")
        return re.sub(r"\s+", " ", t or "").strip()[:800]
    except Exception:
        return ""


def frase(ocr="", alt="", temas=None):
    """Una o dos frases: qué se lee y de qué trata."""
    partes = []
    ocr = re.sub(r"\s+", " ", str(ocr or "")).strip()
    alt = re.sub(r"\s+", " ", str(alt or "")).strip()
    if len(ocr) >= 4:
        partes.append("En la imagen se lee: «" + _acotar(ocr, 160) + "».")
    elif len(alt) > 8:
        partes.append("La imagen muestra: " + _acotar(alt, 120) + ".")
    if temas:
        partes.append("Tema visual: " + ", ".join(t.lower() for t in temas[:3]) + ".")
    if not partes:
        return "Hay una imagen sin texto legible."
    return " ".join(partes)


def analizar(fotos):
    """Lista {id, alt} (capturadas) -> texto OCR, descripción y temas."""
    from app.gustos import clasificar
    from app.imagenes_pub import ruta as ruta_img

    ocrs, alts, frases = [], [], []
    for item in fotos or []:
        if not isinstance(item, dict):
            continue
        alt = (item.get("alt") or "").strip()
        if alt:
            alts.append(alt)
        ident = (item.get("id") or "").strip()
        ocr = ""
        destino = ruta_img(ident) if ident else None
        if destino:
            ocr = leer_texto(destino)
        if ocr:
            item["ocr"] = ocr[:400]
            ocrs.append(ocr)
        mezcla = " ".join(p for p in (alt, ocr) if p)
        temas = clasificar(mezcla)[:3] if mezcla else []
        desc = frase(ocr, alt, temas)
        item["descripcion"] = desc
        if ocr or alt or temas:
            frases.append(desc)
    texto = " ".join(ocrs)
    descripcion = " ".join(frases[:4])
    temas = clasificar(" ".join([texto, descripcion, *alts]))[:5]
    return {
        "texto": texto[:800],
        "descripcion": descripcion[:600],
        "temas": temas,
        "fotos": list(fotos or []),
    }
