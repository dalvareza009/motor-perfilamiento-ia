"""Fotos de publicaciones: se guardan y se describen sin romper el caption."""
import tempfile
from pathlib import Path

import app.imagenes_pub as imagenes_pub
from app.contenido import describir_publicacion
from app.imagenes_pub import dump, guardar_bytes, medida_util, parsear, ruta


def test_guarda_y_lee_una_foto():
    original = imagenes_pub.CARPETA
    imagenes_pub.CARPETA = Path(tempfile.mkdtemp())
    try:
        ident = guardar_bytes(b"\x89PNG" + b"x" * 2000)
        assert ident and ruta(ident).is_file()
        assert ruta("no-es-id") is None
        assert ruta("") is None
        mismo = guardar_bytes(b"\x89PNG" + b"x" * 2000)
        assert mismo == ident
        assert parsear([{"id": ident, "alt": "Con mi hija en el parque"}])[0]["alt"].startswith("Con mi hija")
        assert parsear("no json") == []
        assert "id" in dump([{"id": ident, "alt": "foto"}])
    finally:
        imagenes_pub.CARPETA = original


def test_una_foto_cuenta_aunque_linkedin_aun_no_la_pinte():
    assert medida_util(0, 0, 640, 480) is True
    assert medida_util(120, 80) is True
    assert medida_util(20, 20, 10, 10) is False


def test_describe_usa_el_alt_de_la_foto():
    d = describir_publicacion({
        "texto": "Hoy en familia.",
        "imagenes": [{"id": "abcdabcdabcdabcd", "alt": "Foto con mi hija en el acto de grado"}],
    })
    assert d["tiene_imagenes"] is True
    assert d["n_imagenes"] >= 1
    assert "imagen" in d["resumen"].lower()


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
