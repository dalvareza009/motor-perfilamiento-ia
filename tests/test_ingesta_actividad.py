"""La extracción con sesión se convierte en hechos de perfil, no en CSV."""
from app.ingesta_actividad import hechos_desde_info
from app.perfil_redes import sugerir_productos


def test_ficha_facebook_sale_como_hechos_del_modelo():
    info = {
        "nombre": "Yimy Osvaldo Alvarez Gomez",
        "titular": "Autónomo",
        "ubicacion": "Vive en Segovia (Antioquia). De Remedios",
        "experiencia": "Trabajo declarado en el perfil: Autónomo. Autónomo. Autónomo",
        "educacion": ("Estudios declarados en el perfil: liceo ignacio yepes yepes. "
                      "Universidad de Pamplona. liceo ignacio yepes yepes. "
                      "Universidad de Pamplona. Universidad Distrital Francisco José de Caldas"),
        "estado_civil": "Estado civil declarado en el perfil: Casado. Casado desde 28 de febrero de 2010",
        "familia": "Familia declarada en el perfil: Hermana María Gómez",
        "edad": "Edad declarada en el perfil: 36 años",
    }
    hechos = hechos_desde_info(info)
    por = {h["titulo"]: h["contenido"] for h in hechos}
    assert por["Situacion actual"] == "Autónomo"
    assert "Segovia" in por["Ubicacion"] and "Remedios" in por["Ubicacion"]
    assert por["Trabajo"] == "Autónomo"
    assert "Universidad de Pamplona" in por["Estudios"]
    assert por["Estudios"].count("Universidad de Pamplona") == 1
    assert "Casado" in por["Estado civil"]
    assert "María Gómez" in por["Familia"]
    assert por["Edad"] == "36 años"
    productos = {s["titulo"]: s["contenido"] for s in sugerir_productos(hechos)}
    assert "Seguro de vida" in productos and "Casado" in productos["Seguro de vida"]
    assert "Seguro educativo" in productos


def test_ficha_vacia_no_inventa_hechos():
    assert hechos_desde_info({}) == []
    assert hechos_desde_info(None) == []


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
