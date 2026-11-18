# -*- coding: utf-8 -*-
"""Genera el PDF de revisión de políticas Selenium / Firecrawl."""
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

SALIDA = Path(__file__).with_name(
    "Revision_politicas_tratamiento_datos_Selenium_y_Firecrawl.pdf"
)
FECHA = date(2026, 11, 16)

AZUL = colors.HexColor("#1B3A5C")
AZUL_CLARO = colors.HexColor("#E8EEF4")
GRIS = colors.HexColor("#4A5568")
BORDE = colors.HexColor("#CBD5E1")


def estilos():
    base = getSampleStyleSheet()
    s = {
        "portada_titulo": ParagraphStyle(
            "portada_titulo", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=20, leading=26, textColor=AZUL, alignment=TA_CENTER, spaceAfter=12,
        ),
        "portada_sub": ParagraphStyle(
            "portada_sub", parent=base["Normal"], fontName="Helvetica",
            fontSize=11, leading=15, textColor=GRIS, alignment=TA_CENTER, spaceAfter=6,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=14, leading=18, textColor=AZUL, spaceBefore=16, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=11.5, leading=15, textColor=AZUL, spaceBefore=12, spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"], fontName="Helvetica-Bold",
            fontSize=10.5, leading=13, textColor=colors.HexColor("#2C5282"),
            spaceBefore=8, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName="Helvetica",
            fontSize=9.5, leading=13, textColor=colors.HexColor("#1A202C"),
            alignment=TA_JUSTIFY, spaceAfter=6,
        ),
        "nota": ParagraphStyle(
            "nota", parent=base["Normal"], fontName="Helvetica-Oblique",
            fontSize=8.5, leading=11.5, textColor=GRIS, alignment=TA_JUSTIFY, spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"], fontName="Helvetica",
            fontSize=9.5, leading=12.5, textColor=colors.HexColor("#1A202C"),
            alignment=TA_LEFT, spaceAfter=2,
        ),
        "enlace": ParagraphStyle(
            "enlace", parent=base["Normal"], fontName="Helvetica",
            fontSize=8.5, leading=11.5, textColor=colors.HexColor("#1A202C"),
            spaceAfter=3,
        ),
        "tabla": ParagraphStyle(
            "tabla", parent=base["Normal"], fontName="Helvetica",
            fontSize=8, leading=10.5, textColor=colors.HexColor("#1A202C"),
        ),
        "tabla_h": ParagraphStyle(
            "tabla_h", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=8, leading=10.5, textColor=colors.white,
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"], fontName="Helvetica",
            fontSize=8, textColor=GRIS, alignment=TA_CENTER,
        ),
    }
    return s


def link(url, texto=None):
    t = texto or url
    return f'<link href="{url}" color="#1D4ED8"><u>{t}</u></link>'


def p(estilo, texto):
    return Paragraph(texto, estilo)


def bullets(estilo, items):
    return ListFlowable(
        [ListItem(Paragraph(i, estilo), leftIndent=8, bulletColor=AZUL) for i in items],
        bulletType="bullet", start="•", leftIndent=14, spaceBefore=2, spaceAfter=6,
    )


def tabla(filas, col_widths):
    data = []
    for i, fila in enumerate(filas):
        estilo = estilos()["tabla_h"] if i == 0 else estilos()["tabla"]
        data.append([Paragraph(str(c), estilo) for c in fila])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, AZUL_CLARO]),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def encabezado_pie(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(BORDE)
    canvas.setLineWidth(0.5)
    canvas.line(2 * cm, A4[1] - 1.4 * cm, A4[0] - 2 * cm, A4[1] - 1.4 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRIS)
    canvas.drawString(2 * cm, A4[1] - 1.1 * cm, "Global Seguros · Motor de perfilamiento IA")
    canvas.drawRightString(
        A4[0] - 2 * cm, A4[1] - 1.1 * cm, "Revisión de políticas · Selenium y Firecrawl"
    )
    canvas.line(2 * cm, 1.5 * cm, A4[0] - 2 * cm, 1.5 * cm)
    canvas.drawCentredString(
        A4[0] / 2, 1.0 * cm,
        f"Documento interno · {FECHA.strftime('%d/%m/%Y')} · Página {doc.page}",
    )
    canvas.restoreState()


def construir():
    s = estilos()
    story = []

    # --- Portada ---
    story.append(Spacer(1, 3.2 * cm))
    story.append(p(s["portada_titulo"],
                   "Revisión de políticas de tratamiento de datos"))
    story.append(p(s["portada_sub"],
                   "Selenium (Apache Software Foundation) y Firecrawl "
                   "(SideGuide Technologies Inc.)"))
    story.append(Spacer(1, 0.6 * cm))
    story.append(p(s["portada_sub"],
                   "Documento de apoyo para Global Seguros · Motor de perfilamiento IA"))
    story.append(p(s["portada_sub"],
                   "Fecha de elaboración: 16 de noviembre de 2026"))
    story.append(Spacer(1, 1.2 * cm))
    story.append(p(s["nota"],
                   "Este documento resume información pública de las políticas, "
                   "términos, precios y documentación técnica de ambos proveedores. "
                   "No sustituye un dictamen jurídico ni un acuerdo contractual firmado. "
                   "Las cifras de precios y créditos pueden cambiar; se recomienda "
                   "verificarlas en los enlaces oficiales citados al final de cada sección."))
    story.append(PageBreak())

    # --- 1. Objeto ---
    story.append(p(s["h1"], "1. Objeto y alcance"))
    story.append(p(s["body"],
                   "El motor de perfilamiento usa dos vías distintas para obtener "
                   "información pública de perfiles y del sitio de producto:"))
    story.append(bullets(s["bullet"], [
        "<b>Selenium</b>: automatización local del navegador (Chrome) con la sesión "
        "del asesor. Aplica a LinkedIn, Facebook, Instagram, X, Substack y Reddit "
        "cuando se pulsa «Extraer» en el equipo local.",
        "<b>Firecrawl</b>: API en la nube para leer páginas públicas (por ejemplo "
        "ingesta de perfiles autorizados y del sitio de producto con "
        "<font face='Courier'>FIRECRAWL_API_KEY</font>).",
    ]))
    story.append(p(s["body"],
                   "La pregunta de negocio es sencilla: ¿qué ocurre con los datos "
                   "que pasan por cada herramienta?, ¿los proveedores los usan para "
                   "entrenar modelos?, ¿qué protecciones existen?, ¿cuánto cuestan "
                   "y cómo se gastan los créditos? Este documento responde con base "
                   "en las fuentes oficiales y deja claro dónde la política pública "
                   "aún deja margen de interpretación."))
    story.append(p(s["h2"], "1.1 Hallazgo principal (lectura rápida)"))
    story.append(tabla([
        ["Tema", "Selenium", "Firecrawl (nube)"],
        ["Modelo de servicio",
         "Software libre que corre en el equipo o infraestructura propia",
         "API SaaS gestionada por SideGuide Technologies Inc. (Delaware, EE. UU.)"],
        ["¿El proveedor recibe el contenido del perfil?",
         "No, si WebDriver corre en local. Los datos quedan en el proceso/máquina del motor",
         "Sí. Las URLs y el contenido extraído pasan por sus servidores en EE. UU."],
        ["¿Entrena IA con ese contenido?",
         "No aplica: Selenium no es un servicio de nube que conserve el scrape",
         "La política pública no afirma ni niega de forma explícita el entrenamiento "
         "sobre contenido scrapeado. Sí menciona «caching and indexing» y mejora del "
         "producto. La retención cero (ZDR) es la vía contractual/técnica más clara "
         "para no persistir el contenido"],
        ["Costo de licencia",
         "Gratis (Apache 2.0)",
         "Plan Free con 1.000 créditos/mes; planes de pago desde Hobby"],
        ["Apagar retención / entrenamiento",
         "No hay interruptor: el control es no enviar datos a terceros",
         "ZDR (Enterprise), <font face='Courier'>storeInCache: false</font>, "
         "<font face='Courier'>redactPII</font>, self-host o DPA"],
    ], [3.2 * cm, 6.3 * cm, 7.0 * cm]))
    story.append(PageBreak())

    # --- 2. Selenium ---
    story.append(p(s["h1"], "2. Selenium"))
    story.append(p(s["h2"], "2.1 Qué es y para qué sirve"))
    story.append(p(s["body"],
                   "Selenium es un proyecto de código abierto de la Apache Software "
                   "Foundation para automatizar navegadores. En el motor se usa "
                   "principalmente <b>WebDriver</b>: abre Chrome, navega el perfil "
                   "con la sesión iniciada y lee lo visible. También existen "
                   "Selenium Grid (ejecución distribuida), Selenium IDE (grabación "
                   "de acciones) y Selenium Manager (gestión automática de drivers)."))
    story.append(p(s["body"],
                   "Beneficios prácticos para Global Seguros:"))
    story.append(bullets(s["bullet"], [
        "Trabaja con redes que piden inicio de sesión; la sesión queda en el perfil "
        "de Chrome local, no en un scraper de terceros.",
        "No consume créditos de Firecrawl. La extracción local del lote de redes "
        "no factura API de scraping en la nube.",
        "Permite controlar selectores, tiempos de espera y qué campos se guardan "
        "en PostgreSQL tras el filtro de discernimiento.",
        "Es gratuito y no hay dependencia de un plan comercial del proyecto Selenium.",
    ]))
    story.append(p(s["h2"], "2.2 Cómo se usa (en este proyecto)"))
    story.append(bullets(s["bullet"], [
        "El asesor abre http://127.0.0.1:8000, pega la URL y pulsa Extraer.",
        "Chrome se abre con el perfil de la red correspondiente "
        "(linkedin, facebook, instagram, x, substack, reddit).",
        "Si la red pide login, el usuario inicia sesión y confirma en la interfaz.",
        "El scraper lee ficha, seguidos, publicaciones y reposts; el motor filtra "
        "ruido y guarda hechos pendientes de revisión.",
    ]))
    story.append(p(s["h2"], "2.3 Tratamiento de datos y privacidad"))
    story.append(p(s["body"],
                   "Hay que separar dos planos que a menudo se confunden:"))
    story.append(bullets(s["bullet"], [
        "<b>El software Selenium / WebDriver</b> no es un servicio de almacenamiento "
        "en la nube. Cuando corre en el PC del asesor o en un servidor propio, "
        "el HTML, las cookies de sesión y el texto del perfil pasan por ese entorno. "
        "Selenium HQ no recibe automáticamente esos datos por el solo hecho de usar "
        "la librería.",
        "<b>Los sitios selenium.dev y demás dominios de la ASF</b> sí tienen política "
        "de privacidad (visitas al sitio, logs, Matomo, listas de correo). Eso "
        "regula la navegación de documentación, no el scrape de LinkedIn o Instagram.",
    ]))
    story.append(p(s["body"],
                   "Según la Privacy Policy pública de la Apache Software Foundation "
                   "(vigente a 16/01/2025), al visitar sus sitios se registran IP, "
                   "fecha, URL, referrer, navegador y datos de geolocalización "
                   "aproximada, con retención de logs de 90 días. Matomo anonimiza "
                   "la IP. No hay un «entrenamiento de agentes» sobre el contenido "
                   "que el motor scrapea con WebDriver, porque ese contenido no "
                   "viaja a Apache por usar Selenium."))
    story.append(p(s["h3"], "¿Se puede apagar un entrenamiento?"))
    story.append(p(s["body"],
                   "No existe un interruptor de «no entrenar» en Selenium: no hay "
                   "modelo de IA del proyecto que se alimente con los scrapes del "
                   "cliente. El control real está en la configuración propia: "
                   "dónde corre Chrome, quién tiene acceso al perfil de cookies, "
                   "qué se escribe en la base y qué se envía a otros servicios "
                   "(LLM, Firecrawl, etc.)."))
    story.append(p(s["h2"], "2.4 Costos"))
    story.append(p(s["body"],
                   "Licencia Apache 2.0: uso gratuito, también comercial. Los costos "
                   "reales son de infraestructura propia (equipo, Chrome, eventual "
                   "Grid, tiempo de personal). No hay créditos mensuales ni plan SaaS "
                   "de Selenium HQ."))
    story.append(p(s["h2"], "2.5 Protección y responsabilidades"))
    story.append(bullets(s["bullet"], [
        "La seguridad de cookies y perfiles Chrome depende de Global Seguros "
        "(permisos de carpeta, no versionar cookies, no subir perfiles a git).",
        "Las redes sociales pueden detectar automatización; el uso debe respetar "
        "autorización, términos de cada red y la política interna de tratamientos.",
        "Si en el futuro se usara Selenium Grid en un proveedor cloud de terceros, "
        "habría que revisar el DPA de ese proveedor (BrowserStack, etc.): eso ya "
        "no sería «solo Selenium», sino un hosting de navegadores.",
    ]))
    story.append(p(s["h2"], "2.6 Enlaces oficiales — Selenium / ASF"))
    for texto, url in [
        ("Sitio Selenium", "https://www.selenium.dev/"),
        ("Documentación", "https://www.selenium.dev/documentation/"),
        ("WebDriver", "https://www.selenium.dev/documentation/webdriver/"),
        ("Licencia Apache 2.0 (repositorio)",
         "https://github.com/SeleniumHQ/selenium/blob/trunk/LICENSE"),
        ("Copyright / licencia del proyecto",
         "https://www.selenium.dev/documentation/about/copyright/#license"),
        ("Privacy Policy ASF (sitios públicos)",
         "https://privacy.apache.org/policies/privacy-policy-public.html"),
        ("Contacto privacidad ASF", "mailto:vp-privacy@apache.org"),
        ("Especificación W3C WebDriver", "https://www.w3.org/TR/webdriver/"),
    ]:
        story.append(p(s["enlace"], f"• {texto}: {link(url)}"))
    story.append(PageBreak())

    # --- 3. Firecrawl ---
    story.append(p(s["h1"], "3. Firecrawl"))
    story.append(p(s["h2"], "3.1 Qué es y para qué sirve"))
    story.append(p(s["body"],
                   "Firecrawl (marca comercial de SideGuide Technologies Inc.) es "
                   "una API para buscar, scrapear, rastrear e interactuar con la web, "
                   "devolviendo markdown o JSON listo para LLMs. También ofrece "
                   "Parse (PDF/Office), Agent, Monitor, Interact y el catálogo "
                   "Alexandria de proveedores de datos. Existe versión open source "
                   "autoalojable y un servicio gestionado en la nube."))
    story.append(p(s["body"], "Funcionalidades relevantes:"))
    story.append(bullets(s["bullet"], [
        "<b>Scrape / Crawl / Map</b>: una URL, un sitio o el mapa de URLs.",
        "<b>Search</b>: búsqueda web con opción de scrapear resultados.",
        "<b>Interact</b>: navegador en vivo (clics, formularios).",
        "<b>Agent</b>: investigación estructurada a partir de una instrucción.",
        "<b>Parse</b>: documentos a markdown/JSON.",
        "<b>PII redaction</b>: redacción de datos personales en la salida.",
        "<b>Zero Data Retention (ZDR)</b>: no persistir contenido tras la petición "
        "(plan Enterprise).",
        "<b>Self-host</b>: correr el proyecto open source en infraestructura propia.",
    ]))
    story.append(p(s["h2"], "3.2 Cómo se usa en el motor"))
    story.append(bullets(s["bullet"], [
        "Variable <font face='Courier'>FIRECRAWL_API_KEY</font> en el entorno.",
        "Ingesta de perfiles públicos autorizados y del sitio de producto "
        "(<font face='Courier'>SITIO_DOMINIO</font>).",
        "La extracción con Selenium en local no gasta créditos de Firecrawl.",
        "El balance del equipo se consulta en el dashboard o vía API de uso.",
    ]))
    story.append(p(s["nota"],
                   f"Referencia de saldo al elaborar este documento (cuenta usada "
                   f"en la revisión técnica): periodo de facturación vigente con "
                   f"plan de 1.000 créditos (Free) y saldo restante observado en "
                   f"torno a ese cupo. Verificar siempre en el panel en vivo: "
                   f"{link('https://www.firecrawl.dev/app', 'app Firecrawl')}."))

    story.append(p(s["h2"], "3.3 Tratamiento de datos (política de privacidad)"))
    story.append(p(s["body"],
                   "La Privacy Policy (última revisión citada: 26 de diciembre de 2024) "
                   "indica que Firecrawl puede recolectar nombre, correo, datos de pago, "
                   "información de empresa, IP, navegador, timestamps, page views y "
                   "«information that is collected on behalf of our clients». Usos "
                   "declarados incluyen prestar el servicio, <b>caching and indexing</b>, "
                   "contacto por correo, mejora del producto y del sitio, marketing y "
                   "publicidad."))
    story.append(p(s["body"],
                   "Comparte datos con proveedores como Stripe (pagos), PostHog "
                   "(analítica de producto), Crisp (chat) y Vercel Analytics. Los "
                   "servidores están en Estados Unidos; avisan que el nivel de "
                   "protección puede diferir del de la UE. Cifrado en tránsito (TLS); "
                   "cifrado en reposo «si se solicita». Retención de PII de cuenta: "
                   "hasta solicitud de borrado por escrito; no describen aún una "
                   "política de borrado periódico automático."))
    story.append(p(s["h3"], "¿Usan los datos scrapeados para entrenar agentes o modelos?"))
    story.append(p(s["body"],
                   "En la documentación pública revisada <b>no aparece una frase "
                   "del tipo «no entrenamos modelos con el contenido de tus scrapes»</b>, "
                   "ni tampoco una cláusula que diga explícitamente lo contrario. "
                   "Lo que sí está documentado:"))
    story.append(bullets(s["bullet"], [
        "La política lista «Caching and indexing» y «To determine how to improve "
        "our product» entre los usos de la información.",
        "Los Términos (revisión 7 de octubre de 2026) otorgan a Firecrawl una "
        "licencia amplia sobre contenido generado por el usuario y feedback "
        "publicado en sus Servicios (sección 8.d), lo cual es distinto del "
        "payload de una API de scrape, pero muestra el marco contractual de "
        "reutilización de aportes del usuario.",
        "La vía más clara para que el contenido <b>no se persista</b> tras la "
        "petición es Zero Data Retention en plan Enterprise "
        "(<font face='Courier'>zeroDataRetention: true</font> / "
        "<font face='Courier'>enterprise: [\"zdr\"]</font> en search).",
        "En planes sin ZDR, se puede pedir <font face='Courier'>storeInCache: false</font> "
        "para no cachear el resultado de esa solicitud; el valor por defecto "
        "tiende a servir desde caché cuando aplica.",
        "Self-host: el contenido no sale a la nube de Firecrawl.",
    ]))
    story.append(p(s["nota"],
                   "Recomendación operativa: si el área legal exige certeza contractual "
                   "sobre no entrenamiento / no retención, solicitar por escrito a "
                   "help@firecrawl.com o vía Enterprise (DPA + ZDR) la confirmación "
                   "específica. No dar por sentado un «opt-out de entrenamiento» "
                   "en el plan Free o Hobby solo con la política pública actual."))

    story.append(p(s["h2"], "3.4 Cómo «apagar» retención o reducir exposición"))
    story.append(tabla([
        ["Control", "Disponibilidad", "Cómo se activa"],
        ["Zero Data Retention (ZDR)",
         "Solo Enterprise (hay que habilitarlo en el equipo)",
         "API: <font face='Courier'>zeroDataRetention: true</font> en scrape/crawl/"
         "parse/interact/agent. Search: <font face='Courier'>enterprise: [\"zdr\"]</font> "
         "o <font face='Courier'>[\"anon\"]</font>. Costo: +1 crédito/página en scrape"],
        ["No guardar en caché",
         "API (planes con scrape)",
         "<font face='Courier'>storeInCache: false</font> en la solicitud"],
        ["Redacción de PII",
         "Incluido en planes (según tabla de pricing)",
         "<font face='Courier'>redactPII: true</font>. Costo: +4 créditos/página"],
        ["DPA (acuerdo de tratamiento)",
         "Standard/Growth/Scale: estándar; Enterprise: custom",
         "Proceso comercial / legal con Firecrawl"],
        ["Self-host open source",
         "Gratuito (infraestructura propia)",
         "Despliegue según docs de self-host; los datos no van al SaaS"],
        ["Borrado de datos de cuenta",
         "Todos (derechos CCPA/GDPR vía correo)",
         "Solicitud escrita a help@firecrawl.com"],
    ], [3.5 * cm, 4.5 * cm, 8.5 * cm]))
    story.append(p(s["body"],
                   "Con ZDR, Firecrawl indica que el contenido de página y los datos "
                   "extraídos se procesan en memoria y no se almacenan después de la "
                   "respuesta. En Agent, el resultado puede consultarse 24 horas y "
                   "luego se elimina. Residency: solo Estados Unidos (no ofrecen "
                   "residencia UE)."))

    story.append(p(s["h2"], "3.5 Seguridad y cumplimiento declarados"))
    story.append(bullets(s["bullet"], [
        "SOC 2 Type II (auditoría anual de renovación en curso, según su sitio).",
        "Penetration testing y MFA.",
        "Trust Center con políticas y lista de subprocesadores.",
        "SSO/SCIM, restricciones de IP y de API key: Enterprise.",
        "Bajo GDPR/CCPA, Firecrawl se presenta como encargado (processor) y el "
        "cliente como responsable (controller) del scrape: la base legal y la "
        "minimización siguen siendo de Global Seguros.",
    ]))
    story.append(p(s["h2"], "3.6 Usos prohibidos (términos)"))
    story.append(p(s["body"],
                   "Entre otras, los términos prohíben usar el servicio en violación "
                   "de GDPR/CCPA, para fines de Fair Credit Reporting Act, cobro de "
                   "deudas, background checks duros, elegibilidad de licencias "
                   "gubernamentales, agencias de inteligencia o fines probatorios "
                   "de persecución penal. También prohíben difundir datos personales "
                   "ajenos sin permiso. Esto es relevante en un contexto asegurador: "
                   "el perfilamiento debe apoyarse en autorización y usos permitidos "
                   "por la ley colombiana y la política interna."))
    story.append(PageBreak())

    story.append(p(s["h1"], "4. Costos y créditos de Firecrawl"))
    story.append(p(s["h2"], "4.1 Planes (precios publicados; vigentes según pricing "
                            "con efecto citado desde 4 de septiembre de 2026)"))
    story.append(p(s["nota"],
                   "Los montos «/month» de la tabla inferior corresponden al precio "
                   "con facturación anual, salvo que se indique el precio mensual "
                   "suave. Confirmar siempre en la página de pricing."))
    story.append(tabla([
        ["Plan", "Créditos / mes", "Precio orientativo", "Concurrencia"],
        ["Free", "1.000", "USD 0 (sin tarjeta)", "2"],
        ["Hobby", "5.000", "USD 16/mes (anual) · 19/mes (mensual)", "5"],
        ["Standard", "100.000", "USD 83/mes (anual) · 99/mes (mensual)", "25"],
        ["Growth", "500.000", "USD 333/mes (anual) · 399/mes (mensual)", "50"],
        ["Scale", "1.000.000", "USD 599/mes (anual) · 749/mes (mensual)", "100"],
        ["Enterprise", "A medida", "Custom (+ ZDR, SSO, SLA, DPA custom)", "Custom"],
    ], [2.8 * cm, 3.2 * cm, 7.5 * cm, 3.0 * cm]))
    story.append(p(s["h2"], "4.2 Cómo se gastan los créditos"))
    story.append(tabla([
        ["Operación", "Créditos"],
        ["Scrape (página básica)", "1 / página"],
        ["Crawl", "1 / página"],
        ["Map", "1 / llamada"],
        ["Search", "2 / cada 10 resultados"],
        ["Interact", "2 / minuto de navegador"],
        ["Monitor", "1 / página / chequeo (motores avanzados pueden ser más)"],
        ["JSON / Question / Highlight en scrape", "+4 / página"],
        ["Redacción PII", "+4 / página"],
        ["Zero Data Retention en scrape", "+1 / página"],
        ["Agent", "5 ejecuciones diarias gratis; luego precio dinámico"],
        ["Scrape sin documento de vuelta", "0"],
        ["Página con error 403/404 pero documento devuelto", "1"],
    ], [10.5 * cm, 6.0 * cm]))
    story.append(p(s["body"],
                   "Pay-as-you-go (planes de pago): al agotar el cupo se recargan "
                   "créditos en incrementos de USD 5 (1.000 a 5.000 créditos según "
                   "el plan). Se puede fijar un tope mensual o poner 0 para "
                   "desactivarlo. Los créditos del plan Free/Hobby/Standard/Growth "
                   "no rotan al mes siguiente; Scale rota un mes; Enterprise es "
                   "custom. Los créditos comprados extra permanecen hasta usarse "
                   "(expiran si se cancela la suscripción)."))
    story.append(p(s["h2"], "4.3 Enlaces oficiales — Firecrawl"))
    for texto, url in [
        ("Privacy Policy", "https://www.firecrawl.dev/privacy-policy"),
        ("Terms of Service", "https://www.firecrawl.dev/terms-of-service"),
        ("Third-Party Data Terms", "https://www.firecrawl.dev/terms/third-party-data"),
        ("Pricing y tabla de créditos", "https://www.firecrawl.dev/pricing"),
        ("Enterprise (ZDR, DPA, SSO)", "https://www.firecrawl.dev/enterprise"),
        ("Security overview (docs)", "https://docs.firecrawl.dev/security"),
        ("ZDR — explicación detallada",
         "https://docs.firecrawl.dev/security#data-handling-and-zero-data-retention"),
        ("Blog: Zero Data Retention", "https://www.firecrawl.dev/blog/zero-data-retention"),
        ("Scrape (storeInCache, redactPII, ZDR)",
         "https://docs.firecrawl.dev/features/scrape"),
        ("Self-host", "https://docs.firecrawl.dev/contributing/self-host"),
        ("GDPR/CCPA (processor vs controller)",
         "https://www.firecrawl.dev/glossary/web-scraping-apis/web-scraping-gdpr-ccpa-compliance"),
        ("Trust Center", "https://trust.firecrawl.dev/"),
        ("Subprocessors", "https://trust.firecrawl.dev/subprocessors"),
        ("Status", "https://status.firecrawl.dev/"),
        ("Documentación general", "https://docs.firecrawl.dev"),
        ("Contacto / soporte", "mailto:help@firecrawl.com"),
        ("Contact sales (Enterprise)", "https://www.firecrawl.dev/contact-sales"),
        ("Stripe Privacy (pagos)", "https://stripe.com/privacy"),
        ("PostHog Privacy", "https://posthog.com/privacy"),
        ("Crisp Privacy", "https://crisp.chat/en/privacy/"),
        ("Vercel Privacy", "https://vercel.com/legal/privacy-policy"),
    ]:
        story.append(p(s["enlace"], f"• {texto}: {link(url)}"))
    story.append(PageBreak())

    # --- 5. Comparación y motor ---
    story.append(p(s["h1"], "5. Comparación aplicada al motor de perfilamiento"))
    story.append(tabla([
        ["Criterio", "Selenium (Extraer local)", "Firecrawl (API)"],
        ["Datos de redes con sesión",
         "Adecuado (Chrome + cookies locales)",
         "Limitado / bloqueado en varias redes; no sustituye el login del asesor"],
        ["Sitio de producto / páginas abiertas",
         "Posible, pero más costoso de mantener",
         "Adecuado (markdown limpio, crawl, search)"],
        ["Créditos",
         "0 hacia Firecrawl",
         "Sí; 1 página básica ≈ 1 crédito"],
        ["Residencia de datos del scrape",
         "Equipo/servidor de Global",
         "EE. UU. (SaaS), salvo self-host o ZDR sin persistencia"],
        ["Revisión humana de hechos",
         "Igual: hechos quedan pendientes en el motor",
         "Igual"],
    ], [3.5 * cm, 6.5 * cm, 6.5 * cm]))
    story.append(p(s["h2"], "5.1 Lectura para cumplimiento interno"))
    story.append(bullets(s["bullet"], [
        "Con Selenium local, el riesgo de tratamiento por un encargado externo "
        "sobre el contenido del perfil es bajo: el encargado no es Selenium HQ.",
        "Con Firecrawl SaaS, Global Seguros actúa como responsable del tratamiento "
        "del scrape y Firecrawl como encargado tecnológico; conviene DPA si el "
        "volumen o la sensibilidad lo exigen, y ZDR si se necesita no retención.",
        "Ninguna de las dos herramientas libera a Global Seguros de obtener "
        "autorización del titular, respetar la ley aplicable y no usar datos "
        "restringidos (p. ej. salario en mensajes al cliente).",
        "El filtro de discernimiento del motor reduce qué se guarda, pero no "
        "cambia el hecho de que Firecrawl haya procesado la URL en sus servidores.",
    ]))

    story.append(p(s["h1"], "6. Conclusiones"))
    story.append(p(s["body"],
                   "Selenium y Firecrawl resuelven problemas distintos. Selenium "
                   "da control local y cero factura de API de scraping; la privacidad "
                   "del scrape depende de cómo Global Seguros opere el equipo y la "
                   "base de datos. Firecrawl acelera la lectura de web pública y "
                   "documentos, con costos por crédito, SOC 2 y controles fuertes "
                   "(ZDR, PII, DPA) concentrados en planes superiores."))
    story.append(p(s["body"],
                   "Sobre entrenamiento de agentes: en Selenium no hay un canal "
                   "de entrenamiento del proveedor sobre los perfiles. En Firecrawl, "
                   "la documentación pública enfatiza servicio, caché/indexación y "
                   "mejora de producto, y ofrece ZDR para no persistir contenido; "
                   "no publica un interruptor genérico de «no entrenar» en el plan "
                   "gratuito. Para cerrar esa duda ante auditoría, la vía correcta "
                   "es confirmarlo por escrito y, si aplica, contratar Enterprise "
                   "con ZDR y DPA, o autoalojar."))
    story.append(Spacer(1, 0.4 * cm))
    story.append(p(s["nota"],
                   "Fuentes consultadas en noviembre de 2026 mediante las URLs "
                   "listadas en las secciones 2.6 y 4.3. Cualquier decisión de "
                   "compra o de tratamiento debe contrastarse con Legal/Cumplimiento "
                   "de Global Seguros y con la versión vigente de cada política."))

    doc = SimpleDocTemplate(
        str(SALIDA),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm,
        title="Revisión de políticas Selenium y Firecrawl — Global Seguros",
        author="Motor de perfilamiento IA",
    )
    doc.build(story, onFirstPage=encabezado_pie, onLaterPages=encabezado_pie)
    print(SALIDA)


if __name__ == "__main__":
    construir()
