"""Pruebas de la comparación de clientes (sin BD).  Ejecutar:  python -m tests.test_deduplicacion"""
from app.deduplicacion import (AUTO, REVISION, Grupos, comparar, jaro_winkler, pares_candidatos, sim_nombre,
                               sim_texto)


def reg(i, nombre, **kw):
    base = {"id_registro": i, "nombre": nombre, "genero": None, "edad": None, "correo": None, "celular": None,
            "ciudad": None, "profesion": None, "universidad": None}
    return {**base, **kw}


LAURA_3 = reg(3, "Laura Gómez", genero="Femenino", edad=31, correo="laura.gomez@email.com", celular="3156789234",
              ciudad="Cali", profesion="Diseñadora", universidad="Icesi")
LAURA_8 = reg(8, "Laura Gomez", genero="Femenino", edad=32, celular="3156789234", ciudad="Cali",
              profesion="Diseñadora Gráfica", universidad="Icesi")


def test_jaro_winkler_valores_conocidos():
    assert round(jaro_winkler("martha", "marhta"), 3) == 0.961
    assert round(jaro_winkler("dwayne", "duane"), 2) == 0.84
    assert jaro_winkler("ana", "ana") == 1.0 and jaro_winkler("", "ana") == 0.0


def test_nombres_sin_tildes_mayusculas_ni_orden():
    assert sim_nombre("Laura Gómez", "LAURA GOMEZ") == 1.0
    assert sim_nombre("Pérez Carlos", "Carlos Perez") == 1.0
    assert sim_nombre("Juan López", "Juan Manuel López") >= 0.90
    assert sim_nombre("Jhon Pérez", "John Perez") >= 0.90
    assert sim_nombre("Mariana López", "Juan Manuel López") < 0.80
    assert sim_nombre(None, "Ana") is None


def test_profesion_y_universidad_por_contencion():
    assert sim_texto("Diseñadora", "Diseñadora gráfica") == 1.0
    from app.deduplicacion import VACIAS_UNIVERSIDAD
    assert sim_texto("EAFIT", "Systems Engineering student at EAFIT University", VACIAS_UNIVERSIDAD) == 1.0


def test_laura_se_une_sola_aunque_falte_el_correo_y_la_edad_difiera():
    puntaje, detalle = comparar(LAURA_3, LAURA_8)
    assert puntaje >= AUTO, detalle
    motivos = " ".join(d["motivo"] for d in detalle)
    assert "mismo celular" in motivos and "mismo nombre" in motivos and "1 año" in motivos


def test_familiares_que_comparten_celular_no_se_unen():
    madre = reg(1, "Marta Ruiz", genero="Femenino", edad=58, celular="3001112233", ciudad="Medellín")
    hijo = reg(2, "Santiago Ruiz", genero="Masculino", edad=24, celular="3001112233", ciudad="Medellín")
    puntaje, _ = comparar(madre, hijo)
    assert puntaje < REVISION


def test_homonimos_con_contactos_distintos_no_se_unen():
    a = reg(1, "Juan López", edad=30, correo="juan1@x.com", celular="3000000001", ciudad="Medellín")
    b = reg(2, "Juan López", edad=30, correo="juan2@x.com", celular="3000000002", ciudad="Medellín")
    puntaje, _ = comparar(a, b)
    assert puntaje < AUTO


def test_mismo_nombre_sin_contacto_va_a_revision():
    a = reg(1, "Andrés Ruiz", genero="Masculino", edad=42, ciudad="Medellín", profesion="Médico")
    b = reg(2, "Andres Ruiz", genero="Masculino", edad=42, ciudad="Medellín", profesion="Medico")
    puntaje, _ = comparar(a, b)
    assert REVISION <= puntaje < AUTO


def test_bloques_juntan_lo_comparable_y_no_todo_contra_todo():
    regs = [LAURA_3, LAURA_8, reg(5, "Mariana López", correo="mariana@x.com", celular="3123456789"),
            reg(9, "Juan Manuel López", correo="jm@x.com", celular="3015360782")]
    pares, omitidos = pares_candidatos(regs)
    assert (3, 8) in pares and (3, 5) not in pares and not omitidos


def test_grupos_respetan_los_pares_marcados_como_distintos():
    g = Grupos({1: 1, 2: 2, 3: 3})
    prohibidos = {frozenset((1, 3))}
    g.unir(1, 2)
    assert g.de[2] == 1 and g.miembros[1] == {1, 2}
    assert not g.puede_unir(1, 3, prohibidos)        # 3 es distinto de 1, aunque se parezca a 2


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
