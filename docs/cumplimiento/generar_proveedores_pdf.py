# -*- coding: utf-8 -*-
"""PDF de tratamiento de datos de Selenium y Firecrawl, aplicado al motor."""
from datetime import date
from pathlib import Path
import shutil

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

SALIDA = Path(__file__).with_name("proveedores-extraccion.pdf")
COPIA_ESCRITORIO = Path.home() / "OneDrive - Global" / "Escritorio" / "Selenium_Firecrawl_Tratamiento_Datos.pdf"
COPIA_DESCARGAS = Path.home() / "Downloads" / "Selenium_Firecrawl_Tratamiento_Datos.pdf"
FECHA = date(2026, 11, 18)

AZUL = colors.HexColor("#1B3A5C")
AZUL_CLARO = colors.HexColor("#E8EEF4")
GRIS = colors.HexColor("#4A5568")
BORDE = colors.HexColor("#CBD5E1")


def estilos():
    base = getSampleStyleSheet()
    return {
        "portada_titulo": ParagraphStyle(
            "portada_titulo", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=20, leading=26, textColor=AZUL, alignment=TA_CENTER, spaceAfter=12),
        "portada_sub": ParagraphStyle(
            "portada_sub", parent=base["Normal"], fontName="Helvetica",
            fontSize=11, leading=15, textColor=GRIS, alignment=TA_CENTER, spaceAfter=6),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=14, leading=18, textColor=AZUL, spaceBefore=14, spaceAfter=8),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=11.5, leading=15, textColor=AZUL, spaceBefore=10, spaceAfter=6),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName="Helvetica",
            fontSize=9.5, leading=13, textColor=colors.HexColor("#1A202C"),
            alignment=TA_JUSTIFY, spaceAfter=6),
        "nota": ParagraphStyle(
            "nota", parent=base["Normal"], fontName="Helvetica-Oblique",
            fontSize=8.5, leading=11.5, textColor=GRIS, alignment=TA_JUSTIFY, spaceAfter=6),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"], fontName="Helvetica",
            fontSize=9.5, leading=12.5, alignment=TA_LEFT, spaceAfter=2),
        "enlace": ParagraphStyle(
            "enlace", parent=base["Normal"], fontName="Helvetica",
            fontSize=8.5, leading=11.5, spaceAfter=3),
        "tabla": ParagraphStyle(
            "tabla", parent=base["Normal"], fontName="Helvetica",
            fontSize=8, leading=10.5),
        "tabla_h": ParagraphStyle(
            "tabla_h", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=8, leading=10.5, textColor=colors.white),
    }


def link(url, texto=None):
    return f'<link href="{url}" color="#1D4ED8"><u>{texto or url}</u></link>'


def p(s, estilo, texto):
    return Paragraph(texto, s[estilo])


def bullets(s, items):
    return ListFlowable(
        [ListItem(Paragraph(i, s["bullet"]), leftIndent=8, bulletColor=AZUL) for i in items],
        bulletType="bullet", start="•", leftIndent=14, spaceBefore=2, spaceAfter=6)


def tabla(s, filas, anchos):
    data = []
    for i, fila in enumerate(filas):
        estilo = s["tabla_h"] if i == 0 else s["tabla"]
        data.append([Paragraph(str(c), estilo) for c in fila])
    t = Table(data, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
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


def pie(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(BORDE)
    canvas.setLineWidth(0.4)
    canvas.line(2 * cm, A4[1] - 1.4 * cm, A4[0] - 2 * cm, A4[1] - 1.4 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRIS)
    canvas.drawString(2 * cm, A4[1] - 1.1 * cm, "Selenium y Firecrawl | Tratamiento de datos y condiciones de uso")
    canvas.drawRightString(A4[0] - 2 * cm, A4[1] - 1.1 * cm, str(doc.page))
    canvas.line(2 * cm, 1.5 * cm, A4[0] - 2 * cm, 1.5 * cm)
    canvas.restoreState()


def cuerpo(s):
    """Texto del PDF original, más el cuadro de cuándo entra cada herramienta."""
    story = []
    story.append(p(s, "portada_titulo", "Selenium y Firecrawl"))
    story.append(p(s, "portada_sub",
                   "Tratamiento de datos, privacidad, seguridad, funcionalidades y condiciones económicas"))
    story.append(p(s, "body",
                   "Las dos tecnologías permiten automatizar la obtención de información desde páginas web, "
                   "pero tienen modelos operativos diferentes. Selenium es software de automatización de "
                   "navegadores que puede ejecutarse dentro de una infraestructura controlada por su operador. "
                   "Firecrawl ofrece una API gestionada que procesa solicitudes y contenidos en su propia "
                   "infraestructura, además de una modalidad de despliegue autónomo. Esta diferencia determina "
                   "qué proveedor tiene acceso a los datos, qué condiciones contractuales son relevantes y qué "
                   "controles técnicos se necesitan."))

    story.append(p(s, "h1", "1. Comparación esencial"))
    story.append(tabla(s, [
        ["Aspecto", "Selenium", "Firecrawl Cloud"],
        ["Naturaleza",
         "Biblioteca y componentes de automatización de navegadores, de código abierto.",
         "Servicio API comercial para extracción, búsqueda, rastreo y transformación de contenido web."],
        ["Contenido procesado",
         "No se remite automáticamente al proyecto Selenium si WebDriver se ejecuta en un entorno propio.",
         "Las URL, las consultas y el contenido requerido son procesados en el entorno del proveedor y, según la función, por proveedores subyacentes."],
        ["Entrenamiento con datos",
         "No existe un servicio de entrenamiento de IA asociado a los datos procesados localmente mediante WebDriver.",
         "No hay confirmación pública inequívoca de uso para entrenamiento ni una exclusión general verificable para todos los planes."],
        ["Retención",
         "La establece la implementación: navegador, registros, base de datos y servidores operados.",
         "Incluye mecanismos de caché; ZDR es un control diferenciado habilitado para Enterprise."],
        ["Precio",
         "Licencia sin costo y sin créditos mensuales; infraestructura y operación a cargo del usuario.",
         "Plan gratuito y suscripciones con créditos mensuales, recargos por funciones y posibles consumos adicionales."],
    ], [3.4 * cm, 6.55 * cm, 6.55 * cm]))
    story.append(p(s, "body",
                   "Una evaluación de privacidad debe separar tres cuestiones que no son equivalentes: procesar "
                   "datos para prestar el servicio, retener copias después del procesamiento y reutilizarlos para "
                   "desarrollo o entrenamiento. La ausencia de almacenamiento permanente no demuestra, por sí sola, "
                   "una prohibición contractual de entrenamiento; tampoco una política genérica de mejora del "
                   "producto prueba que efectivamente se entrenen modelos con cada solicitud."))

    story.append(p(s, "h1", "1.1 Cuándo entra cada uno en este motor"))
    story.append(p(s, "body",
                   "La elección queda hecha antes de leer la primera página. Cada tarea usa una sola herramienta "
                   "de principio a fin. Quien opera el motor lo ve por el botón que pulsa y por lo que se abre "
                   "en el equipo."))
    story.append(tabla(s, [
        ["Aspecto", "Selenium", "Firecrawl Cloud"],
        ["Quién lo pone en marcha",
         "Quien está en Perfiles públicos (http://127.0.0.1:8000) y pulsa Extraer en la tarjeta de esa red: LinkedIn, Facebook, Instagram, X, Substack o Reddit. En la página de Facebook, el botón equivalente es Extraer interactuantes.",
         "Quien lanza la ingesta del sitio en Conocimiento, o el lote de perfiles autorizados. Por consola: python -m app.ingesta_web (catálogo) y python -m app.ingesta_perfiles (lote). El botón Extraer no llama a esta API."],
        ["Momento en que empieza el scraping",
         "En el clic de Extraer, con la URL ya pegada en esa tarjeta. En ese instante se abre Chrome en este equipo, con el perfil de esa red, y lee esa URL: ficha, a quién sigue, publicaciones y reposts, hasta el tope de la sesión (máximo 10 publicaciones).",
         "En el instante en que se confirma la ingesta y existe FIRECRAWL_API_KEY. Cada página de globalseguroscolombia.com sale entonces hacia la API. En el lote, LinkedIn pide primero la ficha FullEnrich y, si no trae trabajo, estudios, ciudad, bio ni contacto, pide Apollo; Instagram pide la ficha Oriane; Facebook, X, Substack y Reddit de ese lote se piden como markdown de la página pública."],
        ["Cómo se reconoce cuál está corriendo",
         "Se abre una ventana de Chrome de esa red en el equipo donde corre el servidor. Si la sesión venció, la tarea se detiene y la pantalla pide «Ya inicié sesión». La tarea queda en curso en Perfiles públicos. No se descuentan créditos de Firecrawl.",
         "No se abre Chrome. En el panel de estado, la pastilla Firecrawl indica si hay clave y el dominio del sitio. La tarea figura como ingesta del sitio o ingesta de perfiles. Sin FIRECRAWL_API_KEY esa ingesta no arranca; Extraer en local sigue disponible."],
        ["Cambio de una herramienta a la otra",
         "Durante Extraer no hay relevo. Chrome abre, lee y cierra esa URL con Selenium. Firecrawl no interviene en ese clic, ni si la página falla ni si pide login.",
         "Durante la ingesta no hay relevo hacia Selenium. El único cambio interno está en el lote de LinkedIn: de FullEnrich a Apollo cuando la primera ficha viene vacía. Instagram permanece en Oriane. Las dos fichas salen por la misma API de Firecrawl."],
        ["Dónde corre y qué cuesta ese uso",
         "En el equipo local de Global. Licencia Apache 2.0, cero créditos. En Vercel no hay login manual de redes: la extracción con sesión se hace en local.",
         "En los servidores de Firecrawl (Estados Unidos). Scrape básico: 1 crédito por página. El motor hoy no usa la edición autoalojada."],
        ["Lógica con la que el motor elige",
         "Elige Selenium cuando la acción sale de Perfiles públicos: Extraer, Extraer interactuantes, Extraer lote o leer personas autorizadas. Esas rutas llaman a _abrir_bot. clasificar_url lee el dominio (linkedin.com, instagram.com, facebook.com, x.com, Substack o reddit.com), agrupa las URL por red y abre el Chrome de esa red. Firecrawl no entra en ese camino.",
         "Elige Firecrawl cuando la acción es Iniciar ingesta en Conocimiento, o los comandos python -m app.ingesta_web y python -m app.ingesta_perfiles. Esos módulos crean Firecrawl() y no abren Chrome. En el comando de perfiles, _leer_perfil mira la red y, sin salir de Firecrawl, pide ficha (LinkedIn: FullEnrich y luego Apollo; Instagram: Oriane) o la página en markdown (el resto), porque Firecrawl bloquea abrir LinkedIn e Instagram como página."],
    ], [3.4 * cm, 6.55 * cm, 6.55 * cm]))
    story.append(p(s, "body",
                   "Cómo aplica esa lógica. El motor no mira el texto de la página para cambiar de herramienta. "
                   "La función que atiende el botón ya está escrita para una sola. Si quien opera está en Perfiles "
                   "públicos y pulsa Extraer, la decisión es Selenium antes de abrir la primera URL: se nombra la red "
                   "por el dominio, se abre ese Chrome y se lee la ficha. Si está en Conocimiento y pulsa Iniciar "
                   "ingesta, o si se ejecuta el comando del sitio o el de perfiles autorizados, la decisión es "
                   "Firecrawl. En ese último comando hay un segundo paso, y sigue siendo Firecrawl: la red solo "
                   "define si la llamada es una ficha o la página en markdown."))

    story.append(p(s, "h1", "2. Selenium: funcionamiento y aprovechamiento"))
    story.append(p(s, "h2", "2.1 Capacidades y formas de uso"))
    story.append(p(s, "body",
                   "Selenium WebDriver controla un navegador real mediante interfaces estandarizadas: puede abrir "
                   "páginas, localizar elementos, completar formularios, interactuar con botones, esperar contenido "
                   "dinámico, consultar atributos, capturar pantallas y gestionar ventanas o cookies. Esta capacidad "
                   "resulta útil para pruebas automatizadas de aplicaciones web, verificaciones repetitivas de "
                   "interfaces y, en escenarios jurídicamente permitidos, lectura automatizada de información "
                   "accesible mediante navegador. No convierte por sí mismo HTML en una base de datos depurada: la "
                   "selección de elementos, validación del contenido, gestión de errores y persistencia deben programarse."))
    story.append(p(s, "body",
                   "Sus componentes complementarios incluyen Selenium Grid para distribuir ejecuciones entre distintos "
                   "navegadores o equipos, Selenium IDE para registrar y reproducir flujos y Selenium Manager para "
                   "resolver controladores y, en ciertos escenarios, gestionar versiones de navegador. La configuración "
                   "puede diseñarse para funcionar sobre un equipo propio, contenedores o infraestructura remota; estas "
                   "decisiones afectan de manera directa la exposición de los datos y los costos de operación."))
    story.append(p(s, "h2", "2.2 Flujo de los datos y privacidad"))
    story.append(p(s, "body",
                   "En una ejecución local típica, el programa invoca WebDriver, el navegador establece conexión con "
                   "el sitio web de destino y el código automatizado puede leer el contenido devuelto. Los datos de "
                   "navegación y sesión se encuentran en el equipo o servidor donde opera el navegador; Selenium, "
                   "entendido como biblioteca, no incorpora una API central a la cual envíe automáticamente el texto "
                   "de las páginas. En cambio, el sitio visitado sí puede observar las solicitudes, la dirección IP de "
                   "salida, cookies y otros identificadores, conforme a sus propios términos y políticas."))
    story.append(p(s, "body",
                   "El carácter local no debe confundirse con aislamiento completo. La ejecución puede generar archivos "
                   "de descarga, capturas, registros de consola, trazas, perfiles de navegador o copias en un repositorio "
                   "y enviar resultados a bases de datos, servicios de analítica o modelos de IA conectados por el "
                   "desarrollador. Si se utiliza un Grid externo, una plataforma de navegadores en la nube o una máquina "
                   "administrada por un tercero, es necesario evaluar a ese operador como posible receptor o encargado "
                   "de información."))
    story.append(p(s, "h2", "2.3 ¿Selenium utiliza datos para entrenar modelos de IA?"))
    story.append(p(s, "body",
                   "Respuesta: no, Selenium no utiliza el contenido procesado con WebDriver local para entrenar modelos "
                   "de IA propios. Selenium es una herramienta de automatización del navegador, no un servicio que "
                   "reciba los datos de navegación para desarrollar o entrenar modelos. Al ejecutar WebDriver en un "
                   "equipo controlado por el usuario, el proyecto Selenium no obtiene automáticamente los textos, "
                   "formularios o archivos consultados. Por tanto, no hay un entrenamiento de modelos de Selenium que "
                   "sea necesario desactivar."))
    story.append(p(s, "body",
                   "Este comportamiento se debe a la arquitectura de Selenium: WebDriver transmite instrucciones al "
                   "navegador que se ejecuta en el entorno configurado por el operador y recibe resultados de esa "
                   "automatización. No existe un proceso propio de Selenium que recopile esas páginas para alimentar "
                   "modelos de IA. La exposición a terceros surge únicamente si la implementación incorpora servicios "
                   "externos, como APIs de IA, navegadores remotos o plataformas de analítica, o por la comunicación "
                   "normal del navegador con los sitios visitados. Cada integración debe evaluarse de forma independiente."))
    story.append(p(s, "h2", "2.4 Política de privacidad de Apache Software Foundation"))
    story.append(p(s, "body",
                   "La política de privacidad de la Apache Software Foundation se refiere principalmente a sus sitios, "
                   "servicios en línea y actividades asociadas: contempla registros de visitas, direcciones IP, fechas, "
                   "páginas consultadas, referencias de navegación e información de navegador; informa una retención de "
                   "90 días para determinados registros web y el uso de analítica Matomo en algunos sitios. Esa política "
                   "no debe interpretarse como si autorizara a Apache a recibir todo el contenido que un tercero procese "
                   "localmente con Selenium. Además, la propia página advierte que su implementación puede no estar "
                   "completada en todos los sitios."))
    story.append(p(s, "h2", "2.5 Seguridad, responsabilidades y costos"))
    story.append(p(s, "body",
                   "La licencia Apache 2.0 permite el uso comercial del software sin pago de licencias ni consumo de "
                   "créditos. Los costos que sí pueden surgir son capacidad de cómputo, mantenimiento, desarrollo, "
                   "almacenamiento, redes, proxies o infraestructura de Grid. El operador debe proteger perfiles de "
                   "navegador y credenciales, evitar registros con datos sensibles, definir retenciones y permisos, "
                   "actualizar dependencias y respetar las condiciones del sitio visitado. Selenium no otorga "
                   "autorización para acceder a cuentas ajenas, eludir restricciones ni tratar información personal "
                   "sin una base jurídica suficiente."))

    story.append(p(s, "h1", "3. Firecrawl: funcionalidades y modelo operativo"))
    story.append(p(s, "h2", "3.1 ¿Qué ofrece y qué se puede obtener?"))
    story.append(p(s, "body",
                   "Firecrawl transforma información web en formatos que resultan sencillos de integrar en aplicaciones "
                   "y análisis: texto Markdown, contenido HTML, resultados estructurados y metadatos. Scrape procesa "
                   "una URL; Crawl recorre múltiples páginas de un sitio; Map ayuda a descubrir direcciones; Search "
                   "encuentra resultados en la web; Interact permite sesiones de navegación e interacción; Monitor "
                   "vigila cambios; Parse aborda ciertos documentos, y Agent automatiza tareas de investigación. Sus "
                   "capacidades específicas, límites y recargos varían por endpoint, configuración y plan."))
    story.append(p(s, "body",
                   "La principal ventaja frente a mantener un extractor propio consiste en delegar la resolución de "
                   "páginas con JavaScript, ciertas dificultades de acceso, conversión a formatos legibles, búsqueda "
                   "y escalabilidad. Esa comodidad tiene una contrapartida: al utilizar Firecrawl Cloud, el proveedor "
                   "recibe información necesaria para ejecutar la operación y puede apoyarse en subprocesadores. Para "
                   "organizaciones que priorizan control de infraestructura existe una edición autoalojada, aunque la "
                   "guía oficial advierte que el despliegue inicial no constituye una configuración segura de producción "
                   "ni incluye necesariamente todas las funciones del SaaS."))
    story.append(p(s, "h2", "3.2 ¿Qué datos ingresan y cómo se utilizan?"))
    story.append(p(s, "body",
                   "En la modalidad Cloud se envían a Firecrawl los parámetros de solicitud, por ejemplo URL, consultas "
                   "de búsqueda, formatos de salida, instrucciones de extracción o parámetros de navegación. El servicio "
                   "obtiene el contenido de terceros y devuelve el resultado al cliente. Dependiendo de la modalidad "
                   "pueden existir datos personales dentro de la página, en los parámetros de consulta o en el contenido "
                   "devuelto. La política de privacidad enumera además datos de cuenta y uso —nombre, correo, empresa, "
                   "dirección IP, navegador, fechas, visitas e información obtenida por cuenta de sus clientes—. Los "
                   "fines enumerados abarcan operación del servicio, caché e indexación, gestión comercial y de pagos, "
                   "adaptación del servicio y mejora del producto."))
    story.append(p(s, "body",
                   "Su política señala servidores situados en Estados Unidos y posible circulación de datos a través de "
                   "otros territorios durante el transporte. Identifica integraciones como Stripe para pagos, PostHog "
                   "para analítica, Crisp para conversaciones de soporte y Vercel Analytics. No se debe inferir que "
                   "todos estos terceros reciben automáticamente el contenido íntegro de cada extracción: las categorías "
                   "descritas para cada uno son distintas. La lista de subprocesadores aplicable a datos de clientes "
                   "debe comprobarse en el Trust Center y en el correspondiente acuerdo de tratamiento."))
    story.append(p(s, "h2", "3.3 Uso del contenido para entrenar modelos de IA"))
    story.append(p(s, "body",
                   "La documentación pública no confirma que el contenido enviado a la API se use para entrenar modelos "
                   "propios o de terceros, y tampoco publica una exclusión que lo prohíba en todos los planes. La política "
                   "de privacidad indica que puede utilizar información para prestar el servicio, almacenar en caché, "
                   "indexar y mejorar el producto. No sería correcto afirmar que Firecrawl entrena sus modelos con los "
                   "datos introducidos, ni asegurar que nunca lo hace."))
    story.append(p(s, "body",
                   "No existe un interruptor que se pueda prender o apagar en cualquier momento, en cualquier plan, "
                   "para impedir ese uso. Los controles que sí se pueden activar tienen otro alcance: no guardar el "
                   "resultado en caché, la retención cero del plan Enterprise y la redacción de datos personales en "
                   "la salida. Ninguno equivale, por sí solo, a una prohibición de entrenamiento."))
    story.append(p(s, "h2", "3.4 Retención, caché y eliminación"))
    story.append(p(s, "body",
                   "En Scrape, Firecrawl documenta un mecanismo de caché para acelerar llamadas repetidas. El parámetro "
                   "storeInCache: false pide que el resultado de esa solicitud no se guarde en esa caché; maxAge: 0 "
                   "fuerza una obtención reciente en vez de reutilizar una copia. Ninguno debe presentarse como una "
                   "garantía general de borrado de registros, ausencia de retención por otros subsistemas o prohibición "
                   "de uso para entrenamiento. Además, el uso de resultados previamente almacenados puede mantener el "
                   "consumo normal de créditos."))
    story.append(p(s, "body",
                   "Zero Data Retention (ZDR) es una funcionalidad Enterprise que Firecrawl describe como no persistencia "
                   "del contenido de páginas ni de los datos extraídos más allá de la petición o sesión. Debe habilitarse "
                   "para el equipo y activarse de acuerdo con cada endpoint: en Scrape se indica zeroDataRetention: true; "
                   "en Interact debe configurarse desde la primera llamada; y Search distingue las modalidades "
                   "enterprise: [\"zdr\"] y enterprise: [\"anon\"]. La primera cubre a Firecrawl y al proveedor de "
                   "búsqueda subyacente; en la segunda, este último podría conservar una consulta anonimizada. ZDR no "
                   "significa que el servicio no procese datos mientras ejecuta la solicitud."))
    story.append(p(s, "body",
                   "La documentación pública revisada no establece una exclusión general y verificable del uso de "
                   "información de clientes para entrenar modelos. Tampoco identifica expresamente un uso sistemático "
                   "de los contenidos extraídos con ese fin. Por ello, no es posible concluir que Firecrawl entrene "
                   "modelos con cada solicitud ni garantizar que nunca lo haga. Cuando se procesen datos personales o "
                   "confidenciales, es necesario obtener una confirmación escrita que abarque consultas, instrucciones, "
                   "páginas recuperadas, resultados, registros y eventuales proveedores subyacentes, además de las "
                   "finalidades autorizadas."))
    story.append(p(s, "body",
                   "Los controles publicados permiten reducir la conservación y exposición de los datos, pero tienen "
                   "una finalidad distinta de la del entrenamiento de modelos. El parámetro storeInCache: false evita "
                   "incorporar el resultado de una solicitud a la caché. Zero Data Retention (ZDR), sujeto a habilitación "
                   "Enterprise, limita la persistencia de contenido y resultados después del procesamiento. La redacción "
                   "de datos personales actúa sobre la salida, sin demostrar que los datos originales no se hayan "
                   "procesado. El autoalojamiento ofrece mayor control sobre la infraestructura, siempre que se revisen "
                   "sus dependencias externas."))
    story.append(p(s, "body",
                   "Respecto de los datos personales asociados a la cuenta, la política indica que normalmente se "
                   "conservan hasta que se solicite su eliminación por escrito y que no cuenta aún, en ese texto, con "
                   "un calendario general de eliminación periódica. También establece canales para derechos de acceso, "
                   "corrección o supresión. Antes de aceptar un servicio con datos sensibles, es necesario confirmar "
                   "el tratamiento separado de registros técnicos, copias de seguridad, contenidos temporales y "
                   "devoluciones de proveedores externos."))
    story.append(p(s, "h2", "3.5 Redacción de datos personales y protección de la información"))
    story.append(p(s, "body",
                   "Firecrawl ofrece PII redaction, orientada a suprimir o enmascarar identificadores personales en las "
                   "salidas de Scrape y Parse. Esta función puede reducir el contenido personal que recibe y almacena "
                   "el consumidor final, pero el proveedor pudo necesitar tratar el material original para identificar "
                   "dichos datos; por tanto, la redacción de salida no debe confundirse con anonimización del origen o "
                   "con ausencia de acceso a información por la infraestructura de Firecrawl. Su precisión técnica, "
                   "categorías detectadas y costos deben verificarse según el tipo de llamada."))
    story.append(p(s, "body",
                   "El proveedor declara cumplimiento SOC 2 Type II, medidas de control de acceso y pruebas de "
                   "penetración, cifrado TLS en tránsito y, en su política general, cifrado en reposo si se solicita. "
                   "Para planes empresariales anuncia SSO/SCIM, restricciones de claves e IP, controles de amenazas y "
                   "opciones de auditoría. Estas son declaraciones públicas; una revisión rigurosa debe obtener el "
                   "informe SOC 2 vigente, periodo cubierto, excepciones, alcance de infraestructura, documento DPA, "
                   "subprocesadores, política de incidentes y evidencia del cifrado en reposo aplicable a los datos "
                   "concretos. No existe una garantía absoluta de seguridad."))
    story.append(p(s, "h2", "3.6 Autoalojamiento: ventajas y límites"))
    story.append(p(s, "body",
                   "La versión autoalojada permite controlar API, almacenamiento y redes propias, reduciendo la "
                   "necesidad de remitir contenidos a Firecrawl Cloud si todas las dependencias y proveedores externos "
                   "están configurados de forma interna o aprobada. No implica automáticamente soberanía total: proxies, "
                   "motores de búsqueda, modelos, servicios de navegador u otras integraciones pueden originar "
                   "transferencias independientes. El despliegue exige diseñar autenticación, TLS, persistencia, copias "
                   "de seguridad, monitoreo y actualizaciones. La documentación oficial advierte de una corrección de "
                   "seguridad para resolución de destinos privados, incorporada en versiones recientes, y recomienda "
                   "mantener el entorno actualizado."))

    story.append(p(s, "h1", "4. Planes y créditos de Firecrawl"))
    story.append(p(s, "body",
                   "Los valores siguientes corresponden a las tarifas públicas mostradas por Firecrawl, expresadas en "
                   "dólares estadounidenses, antes de impuestos. Los importes anuales representan el equivalente mensual "
                   "cuando el compromiso se factura por año; no deben confundirse con una suscripción mensual sin "
                   "compromiso. La página identifica modificaciones efectivas desde el 4 de septiembre de 2026."))
    story.append(tabla(s, [
        ["Plan", "Créditos/mes", "USD/mes anual", "USD mensual", "Concurrencia"],
        ["Free", "1.000", "0", "0", "2"],
        ["Hobby", "5.000", "16", "19", "5"],
        ["Standard", "100.000", "83", "99", "25"],
        ["Growth", "500.000", "333", "399", "50"],
        ["Scale", "1.000.000", "599", "749", "100"],
        ["Enterprise", "A medida", "Cotización", "Cotización", "A medida"],
    ], [3.2 * cm, 3.0 * cm, 3.4 * cm, 3.2 * cm, 3.7 * cm]))
    story.append(p(s, "body",
                   "En el plan Free se renuevan 1.000 créditos por mes. Firecrawl publica también límites de llamadas "
                   "por minuto y concurrencia que se amplían por plan; un mayor número de créditos no elimina por sí "
                   "solo los límites operativos. El crédito es una unidad común de consumo de varios endpoints, no una "
                   "página universal para todas las funciones."))
    story.append(tabla(s, [
        ["Operación", "Consumo público indicado", "Precisión relevante"],
        ["Scrape / Crawl", "1 crédito por página básica", "Formatos avanzados pueden sumar cargos."],
        ["Map", "1 crédito por llamada básica",
         "La tabla de detalle presenta una rotulación ambigua; confirmar para casos especiales."],
        ["Search", "2 créditos por 10 resultados", "ZDR integral eleva a 10 créditos por 10 resultados."],
        ["Interact", "2 créditos por minuto de navegador", "Se factura por duración, no por páginas."],
        ["Monitor", "1 crédito/página/comprobación",
         "Extracción determinista avanzada: tarifa diferente (7 créditos/página/comprobación)."],
        ["JSON, Question, Highlight", "+4 créditos/página para Scrape/Crawl",
         "Se adicionan al costo básico cuando aplica."],
        ["ZDR en Scrape", "+1 crédito/página", "Requiere plan Enterprise y habilitación."],
        ["Agent", "5 ejecuciones diarias gratuitas; luego dinámico",
         "No se puede reducir a tarifa fija sin un escenario concreto."],
    ], [4.6 * cm, 6.2 * cm, 5.7 * cm]))
    story.append(p(s, "body",
                   "La página de tarifas indica que las solicitudes Scrape sin resultado no se cobran, mientras que una "
                   "página efectivamente devuelta con respuesta HTTP 403 o 404 puede consumir un crédito. Los créditos "
                   "mensuales no utilizados no pasan al mes siguiente en Free, Hobby, Standard o Growth; Scale permite "
                   "arrastrarlos durante un mes y Enterprise depende del contrato. La compra adicional de créditos y sus "
                   "condiciones de vencimiento deben revisarse en facturación."))
    story.append(p(s, "h2", "4.1 Consumo adicional y ejemplos de cálculo"))
    story.append(p(s, "body",
                   "Firecrawl anuncia recargas pay as you go exclusivamente en planes pagos, en incrementos de USD 5 "
                   "hasta el límite mensual configurado. Por cada USD 5, el cupo publicado varía según el plan: Hobby "
                   "1.000, Standard 2.000, Growth 2.500 y Scale 5.000 créditos adicionales. Para evitar sobrecostos "
                   "conviene fijar un límite de gasto, usar formatos avanzados solamente cuando se necesiten y estimar "
                   "páginas, búsquedas y minutos de interacción por separado."))
    story.append(p(s, "body",
                   "Ejemplo orientativo A. Extraer 300 páginas básicas mediante Scrape equivale a unos 300 créditos, "
                   "sin servicios adicionales. Si todas usan un formato avanzado que suma cuatro créditos por página, "
                   "el costo estimado es 1.500 créditos. Ejemplo B. Procesar 200 páginas con ZDR en Scrape supone "
                   "aproximadamente 400 créditos, siempre que la función esté habilitada en Enterprise. Ejemplo C. "
                   "Una consulta Search que devuelve 20 resultados equivale aproximadamente a cuatro créditos en tarifa "
                   "ordinaria y 20 créditos con ZDR integral. Los cálculos suponen operaciones exitosas y las tarifas "
                   "básicas indicadas; no incluyen consumos independientes de otros endpoints."))
    story.append(p(s, "h2", "4.2 Controles con impacto en costo y privacidad"))
    story.append(p(s, "body",
                   "Es útil separar el control de presupuesto del control de tratamiento de datos. Desactivar la compra "
                   "de créditos adicionales impide extender la facturación, pero no modifica la política de conservación; "
                   "usar storeInCache: false modifica la caché, no el monto de créditos básicos; solicitar la redacción "
                   "de PII puede requerir un tratamiento adicional cuya tarifa específica debe verificarse antes de "
                   "automatizar grandes volúmenes; y activar ZDR requiere una habilitación empresarial, con recargos "
                   "documentados para algunas operaciones."))

    story.append(p(s, "h1", "5. Condiciones legales y verificación necesaria"))
    story.append(p(s, "body",
                   "La legalidad de una extracción no depende únicamente de que la información pueda verse sin "
                   "contraseña. Deben analizarse la finalidad, legitimidad de acceso, condiciones de las plataformas, "
                   "categorías de datos, derechos de los titulares y conservación. Los términos de Firecrawl prohíben "
                   "expresamente determinados usos, entre ellos actividades ilícitas, tratamiento contrario a las leyes "
                   "de privacidad, algunos procedimientos de investigación de antecedentes, cobro de deudas y usos "
                   "sujetos a la Fair Credit Reporting Act de Estados Unidos. Dichas restricciones requieren lectura "
                   "específica si se pretende utilizar información en decisiones sobre personas."))
    story.append(p(s, "body",
                   "En Colombia, la Ley 1581 de 2012 y el Decreto 1074 de 2015 establecen obligaciones de tratamiento "
                   "y reglas diferenciadas para transferencia y transmisión internacional de datos personales. En una "
                   "transmisión a un encargado por cuenta del responsable, el marco reglamentario prevé reglas "
                   "contractuales propias; no debe presumirse que todo envío internacional constituye transferencia ni "
                   "que el simple uso de un proveedor extranjero satisface las condiciones exigidas. La calificación "
                   "depende de las funciones reales, de quién decide las finalidades y del acuerdo aplicable."))
    story.append(p(s, "body",
                   "Para una contratación con datos personales resulta razonable exigir: definición de responsable y "
                   "encargado; categorías de datos; finalidades admitidas; exclusión expresa de entrenamiento de modelos "
                   "cuando sea necesaria; plazos diferenciados para contenido, telemetría y respaldos; subprocesadores "
                   "y ubicaciones; medidas de seguridad; notificación de incidentes; devolución o eliminación al terminar; "
                   "evidencias de auditoría; y procedimiento para solicitudes de titulares. La presencia de ZDR, SOC 2 "
                   "o DPA comercial no reemplaza estas verificaciones."))

    story.append(p(s, "h1", "6. Conclusión técnica"))
    story.append(p(s, "body",
                   "Selenium ofrece mayor control directo sobre los datos cuando toda la automatización y el "
                   "almacenamiento se realizan en infraestructura propia, pero ese control traslada al operador las "
                   "obligaciones de seguridad, cumplimiento, continuidad y mantenimiento. Carece de cuotas de API y de "
                   "una función nativa de entrenamiento de modelos asociada al contenido tratado. Firecrawl Cloud reduce "
                   "la complejidad de extraer y estructurar información web, a cambio de procesar datos en la "
                   "infraestructura del proveedor y facturar operaciones mediante créditos. La política y la documentación "
                   "describen mecanismos de seguridad y retención, pero la exclusión de entrenamiento con contenidos de "
                   "cliente no debe afirmarse sin confirmación contractual específica."))
    story.append(p(s, "body",
                   "Para información pública no sensible, una valoración de riesgo puede admitir controles ordinarios "
                   "según finalidad y contexto. Para contenidos personales, confidenciales o regulados, se requiere una "
                   "valoración reforzada y, antes de su envío a Firecrawl Cloud, una respuesta formal sobre no "
                   "entrenamiento, conservación, subprocesamiento, borrado y ubicación. Si la exigencia es que el "
                   "contenido no salga de una infraestructura determinada, la alternativa técnicamente coherente es "
                   "evaluar automatización local o autoalojamiento con dependencias controladas."))

    story.append(p(s, "h1", "Fuentes oficiales y enlaces de consulta"))
    story.append(p(s, "body",
                   "Los siguientes enlaces permiten consultar directamente las políticas, documentos técnicos y "
                   "condiciones comerciales utilizados. Las tarifas y funcionalidades pueden cambiar; antes de contratar "
                   "o implementar se debe comprobar la versión vigente."))
    for texto, url in [
        ("Selenium, documentación general", "https://www.selenium.dev/documentation/"),
        ("Apache Software Foundation, política pública de privacidad",
         "https://privacy.apache.org/policies/privacy-policy-public.html"),
        ("Selenium, WebDriver", "https://www.selenium.dev/documentation/webdriver/"),
        ("Selenium Grid y ejecución distribuida", "https://www.selenium.dev/documentation/grid/"),
        ("Selenium Manager", "https://www.selenium.dev/documentation/selenium_manager/"),
        ("Selenium, licencia y atribuciones", "https://www.selenium.dev/documentation/about/copyright/"),
        ("Firecrawl, política de privacidad", "https://www.firecrawl.dev/privacy-policy"),
        ("Firecrawl, términos de servicio", "https://www.firecrawl.dev/terms-of-service"),
        ("Firecrawl, seguridad y Zero Data Retention", "https://docs.firecrawl.dev/security"),
        ("Firecrawl, Scrape, caché y parámetros", "https://docs.firecrawl.dev/features/scrape"),
        ("Firecrawl, precios y créditos", "https://www.firecrawl.dev/pricing"),
        ("Firecrawl, Trust Center y subprocesadores", "https://trust.firecrawl.dev/"),
        ("Firecrawl, guía de autoalojamiento", "https://docs.firecrawl.dev/contributing/self-host"),
        ("Firecrawl, términos para datos de terceros", "https://www.firecrawl.dev/terms/third-party-data"),
        ("Firecrawl, contacto comercial Enterprise", "https://www.firecrawl.dev/contact-sales"),
    ]:
        story.append(p(s, "enlace", f"{texto} — {link(url)}"))
    story.append(p(s, "body",
                   "Canales de contacto: privacidad Apache, vp-privacy@apache.org. Soporte y consultas de privacidad "
                   "Firecrawl, help@firecrawl.com."))
    return story


def construir():
    s = estilos()
    story = cuerpo(s)
    doc = SimpleDocTemplate(
        str(SALIDA), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
        title="Selenium y Firecrawl — tratamiento de datos",
        author="Motor de perfilamiento IA",
    )
    doc.build(story, onFirstPage=pie, onLaterPages=pie)
    for destino in (COPIA_ESCRITORIO, COPIA_DESCARGAS):
        if not destino.parent.exists():
            continue
        try:
            shutil.copyfile(SALIDA, destino)
            print(destino)
        except PermissionError:
            alterno = destino.with_name(destino.stem + "_actualizado.pdf")
            shutil.copyfile(SALIDA, alterno)
            print("bloqueado:", destino)
            print(alterno)
    print(SALIDA)


if __name__ == "__main__":
    construir()
