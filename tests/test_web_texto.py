"""Pruebas de extracción (estructura de globalseguroscolombia.com).  Ejecutar:  python -m tests.test_web_texto"""
from app.web_texto import (categoria, enlaces_pdf, familia_por_grupo, fragmentos_pagina, fragmentos_pdf,
                           limpiar, nombre_pdf)

CDN = "https://cdn.globalseguroscolombia.com/public"
MD = f'''
[Ir al contenido](#content)

**Global Seguros de Vida S.A.** informa que, con ocasión del sismo registrado el día de hoy, las sucursales de Manizales, Pereira y Cali permanecerán temporalmente cerradas.

- [Inicio](https://www.globalseguroscolombia.com/)
- [Soluciones](https://www.globalseguroscolombia.com/productos/)
  * [Seguros Educativos](https://www.globalseguroscolombia.com/seguros-educativos/)

## Seguros Educativos

Asegura desde hoy la educación de tus hijos con una solución pensada para planear su futuro con respaldo, confianza y tranquilidad.

[Conocer más](#more-info)

## Nuestras Soluciones

### Cobertura

#### GlobalGarantizada 360º

[¡Lo quiero!](https://www.globalseguroscolombia.com/contactenos/ "GlobalGarantizada 360º")

![Icono check azul]({CDN}/icono.svg "Icono check azul")

Garantizado – 100% pago valor de la matrícula.

### Clausulado y Tarifas

[Ver Clausulado]({CDN}/2026/07/CLAUSULADO-Póliza-GlobalUniversidad-360_.pdf "Ver Clausulado") [Ver Tarifas ![Icono clausula]({CDN}/i.svg "Icono clausula")]({CDN}/2026/09/TARIFAS-GLOBALGARANTIZADA-360-oct-a-dic-2026.pdf "Ver Tarifas")

### GlobalUniversidad Garantizada Platino

[¡Lo quiero!](https://www.globalseguroscolombia.com/contactenos/ "GlobalUniversidad Garantizada Platino")

#### Cobertura

![Icono check azul]({CDN}/icono.svg "Icono check azul")

Garantizado – 100% pago valor de la matrícula.

#### Lugar

![Icono check azul]({CDN}/icono.svg "Icono check azul")

Cualquier Carrera – Cualquier Universidad Pregrado en Colombia.

#### Periodos de cobertura

![Icono check azul]({CDN}/icono.svg "Icono check azul")

Hasta por cinco (5) años de períodos académicos sin exceder diez (10) pagos de matrícula ordinaria.

#### Trámite de pago

[Ver anexo]({CDN}/2026/04/GlobalUniversidad-Garantizada-Platino-.pdf "Ver anexo") [Ver clausulado ![Icono]({CDN}/i.svg "Icono")]({CDN}/2026/04/POLIZA-SEGURO-EDUCATIVO-GlobalUniversidad-Garantizada-Platino-2025.pdf "Ver clausulado")

## Beneficio adicional Seguro de Vida

### Plan 1

#### Cobertura

![Icono check azul]({CDN}/icono.svg "Icono check azul")

Muerte o incapacidad total o permanente

#### Edad máxima de ingreso

![Icono check azul]({CDN}/icono.svg "Icono check azul")

Hasta 55 años

## Preguntas frecuentes

**¿Si decido comprar esta solución para mis dos hijos, tengo derecho a un descuento?**

Global Seguros no maneja descuentos, el valor de nuestras soluciones es el de la tabla de precios vigente.

**¿Puedo trasladar el seguro que compré para mi hijo a otro familiar?**

Sí, se puede trasladar el plan a un nuevo beneficiario que sea hijo del tomador, hermano o medio hermano del beneficiario.

## Contáctanos

Comunícate con nosotros al correo servicioalcliente@globalseguros.co, en Bogotá a la línea 7440084.
'''

MD_PRODUCTOS = '''
## Seguros Educativos

- 						 **Global**Universidad Garantizada Platino

Garantiza el pago de la matrícula universitaria hasta por cinco (5) años o diez (10) períodos académicos sin importar su costo futuro.

- 						 **Global**Semestres

Permite adquirir las soluciones educativas GlobalUniversidad Garantizada mediante la adquisición semestre a semestre hasta completar diez períodos.

[#sol1](#sol1)

## Seguro de Pensión Voluntaria

Ofrecemos la solución de pensión voluntaria que le garantiza una pensión cierta por el período que usted determine, con características flexibles.
'''


def _por_titulo(frags):
    return {f["titulo"]: f for f in frags}


def test_limpieza():
    t = limpiar("Hola [Conoce](https://x.com) ![img](https://x.com/i.png) https://x.com/y **fin**\n¡Lo quiero!\nHola [Conoce](u) fin")
    assert "http" not in t and "img" not in t and "**" not in t and "Lo quiero" not in t


def test_descarta_ruido_del_sitio():
    frags, _ = fragmentos_pagina(MD)
    todo = " ".join(f["contenido"] + f["titulo"] for f in frags)
    for ruido in ("sismo", "Inicio", "Comunícate", "servicioalcliente", "Lo quiero", "Ver clausulado", "Icono"):
        assert ruido not in todo, ruido


def test_producto_con_subsecciones_plegadas():
    frags, omitidos = fragmentos_pagina(MD)
    p = _por_titulo(frags)["GlobalUniversidad Garantizada Platino"]
    assert "Cobertura: Garantizado – 100% pago valor de la matrícula." in p["contenido"]
    assert "Periodos de cobertura: Hasta por cinco (5) años" in p["contenido"]
    assert p["categoria"] == "Producto"
    assert omitidos >= 2                                   # 'Cobertura' y 'Clausulado y Tarifas' genéricos


def test_plan_lleva_el_contexto_del_grupo():
    p = _por_titulo(fragmentos_pagina(MD)[0])["Beneficio adicional Seguro de Vida › Plan 1"]
    assert p["categoria"] == "Beneficio" and "Edad máxima de ingreso: Hasta 55 años" in p["contenido"]


def test_preguntas_frecuentes():
    p = _por_titulo(fragmentos_pagina(MD)[0])
    q = [t for t in p if t.startswith("¿")]
    assert len(q) == 2 and all(p[t]["categoria"] == "Pregunta frecuente" for t in q)
    assert "no maneja descuentos" in p[q[0]]["contenido"]


def test_lista_de_productos_y_familia():
    frags, _ = fragmentos_pagina(MD_PRODUCTOS)
    p = _por_titulo(frags)
    assert "GlobalUniversidad Garantizada Platino" in p and "GlobalSemestres" in p
    assert "#sol1" not in p["GlobalSemestres"]["contenido"]
    assert familia_por_grupo(p["GlobalSemestres"]["grupo"]) == "Seguro educativo"
    assert familia_por_grupo("Seguro de Pensión Voluntaria") == "Seguro de pensión"
    assert familia_por_grupo("Seguro renta vitalicia") == "Seguro renta vitalicia"
    assert familia_por_grupo("Seguros de Vida") == "Seguro de vida"
    assert familia_por_grupo("Seguro Rentas Voluntarias") == "Seguro renta voluntaria"


def test_pdfs_sin_tarifas_por_defecto():
    sin = enlaces_pdf(MD)
    assert len(sin) == 3 and not any("TARIFA" in u for u in sin)
    assert len(enlaces_pdf(MD, incluir_tarifas=True)) == 4
    assert nombre_pdf(sin[0]) == "CLAUSULADO Póliza GlobalUniversidad 360"


def test_categorias():
    assert categoria("Coberturas incluidas") == "Cobertura"
    assert categoria("¿Quién puede contratarlo?") == "Pregunta frecuente"
    assert categoria("Hay preguntas que en la vida se deben hacer") == "Producto"
    assert categoria("EXCLUSIONES GENERALES") == "Exclusión"


def test_pdf_secciones_y_exclusiones():
    texto = ("CONDICIONES GENERALES\n" + "Esta póliza cubre el pago de la matrícula según lo pactado. " * 3 +
             "\n\nEXCLUSIONES\n" + "No se amparan los cargos adicionales del recibo de matrícula. " * 3)
    frags, trunc = fragmentos_pdf(texto, "Póliza Prueba")
    cats = {f["titulo"]: f["categoria"] for f in frags}
    assert cats["Póliza Prueba: CONDICIONES GENERALES"] == "Clausulado"
    assert cats["Póliza Prueba: EXCLUSIONES"] == "Exclusión" and not trunc


def test_troceado_sin_perdida_y_tope():
    largo = " ".join(f"Frase número {i} del clausulado con bastante texto." for i in range(120))
    frags, _ = fragmentos_pdf("ARTÍCULO 1 OBJETO\n" + largo, "Póliza")
    assert len(frags) > 1 and all(len(f["contenido"]) <= 1200 for f in frags)
    assert sum(len(f["contenido"].split()) for f in frags) == len(largo.split())
    _, trunc = fragmentos_pdf("\n".join(f"ARTÍCULO {i} OBJETO\n" + "Texto del artículo con detalle suficiente para pasar. " * 3
                                         for i in range(30)), "P", max_fragmentos=10)
    assert trunc


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("OK ", n)