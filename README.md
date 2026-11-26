# Motor de perfilamiento IA

Herramienta interna de **Global Seguros** para segmentar clientes, preparar borradores de WhatsApp y correo, gestionar el conocimiento de producto y leer **perfiles públicos autorizados**.

Las cifras salen de SQL. El modelo interpreta preguntas y redacta textos; no inventa coberturas ni datos personales. Cada consulta queda en auditoría. Los hechos de redes pasan por revisión humana antes de usarse.

| | |
| --- | --- |
| Código | https://github.com/dalvareza009/motor-perfilamiento-ia |
| App (Vercel) | https://motor-perfilamiento-ia.vercel.app |
| Rama de trabajo actual | `cursor/facebook-pagina-interactuantes-y-gustos` |

## Qué hace

- **Panel y segmentos:** conteos, k-anonimato para el rol analista, plantillas por grupo.
- **Clientes:** ficha, hechos de perfil, perfil IA, borradores por canal.
- **Asistente:** pregunta en lenguaje natural → intención (LLM) → SQL o generación de mensajes.
- **Borradores:** validación automática y estados (borrador → revisión → aprobado → enviado).
- **Conocimiento:** ingesta del sitio con Firecrawl, aprobación humana, búsqueda vectorial si hay embeddings.
- **Perfiles públicos:** LinkedIn, Facebook, Instagram, X, **Substack** y **Reddit**, con sesión de Chrome de quien opera.
- **Duplicados y auditoría.**

### Roles

| Rol | Alcance |
| --- | --- |
| Analista | Cifras agregadas, resúmenes y plantillas. Grupos con menos de 5 personas se ocultan. |
| Asesor | Lo anterior más fichas y borradores individuales o en lote. |
| Administrador | Lo anterior más conocimiento, perfiles, duplicados, ingesta y auditoría. |

## Estructura del repositorio

```
app/                 API FastAPI y reglas de negocio
frontend/            Interfaz (HTML/JS/CSS)
*_scraper.py         Extractores por red (Selenium + Chrome)
docs/
  cumplimiento/      Privacidad y proveedores de extracción
  arquitectura/      Diagramas
data/                Perfiles autorizados (no versionar datos reales sensibles)
tests/               Pruebas
scripts/             Arranque local, despliegue y utilidades
```

Los nombres de carpetas y archivos describen el contenido (`cumplimiento`, `arquitectura`), no el texto de un pedido puntual.

## Requisitos

- Python 3.12+
- Google Chrome
- PostgreSQL 18 (local) o Neon (`DATABASE_URL`)
- Ollama en local (`qwen3:4b-instruct`, `nomic-embed-text`) **o** API compatible (`LLM_*` / AI Gateway en Vercel)

## Instalación y arranque local

Para otro computador: descomprime el paquete de equipo y sigue **[INSTALAR.md](INSTALAR.md)** (o `INSTALAR.bat`). Las claves no van en el zip.

```powershell
copy .env.example .env
# En .env: comenta DATABASE_URL y LLM_*; descomenta DB_* y OLLAMA_*
# Ajusta DB_PASSWORD

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\scripts\restaurar-base.ps1          # si tienes datos_iniciales/base_datos.sql
.\.venv\Scripts\python.exe -m app.api
```

También: `scripts\preparar-equipo.ps1` y luego `scripts\iniciar.ps1`.

Abrir http://127.0.0.1:8000 — usuario a elección, clave vacía si no hay `DEMO_CLAVE`, rol Administrador.

Guía adicional: [README-ejecucion-local.md](README-ejecucion-local.md).

## Extracción de perfiles

Solo perfiles en `data/perfiles_autorizados.json` con autorización marcada.

1. Rol administrador → **Perfiles públicos**.
2. Pegar la URL (LinkedIn, Facebook, Instagram, X, Substack o Reddit).
3. Extraer. Chrome se abre: iniciar sesión en esa red y confirmar en la web.
4. Los hechos quedan pendientes de revisión; los aprobados se usan en borradores.

En todas las redes se busca, si está dicho o se ve: a quién sigue, intereses de vida, publicaciones y reposts útiles para acercarnos, estado civil, hijos, escolaridad, empresa, dónde estudió y el rango salarial solo si la persona lo publica (para el asesor; **nunca** en el mensaje al cliente). El meme, el clima y el ruido de interfaz no entran.

**Substack:** bio, posts y restacks; OCR/resumen de imágenes cuando aplica.  
**Reddit:** posts y comentarios útiles para el perfil comercial; se descartan memes y meta de karma.

No versionar `*.json` de cookies ni carpetas `chrome_*_profile`.

## Cumplimiento: Selenium y Firecrawl

El motor obtiene contenido web por dos vías:

| Vía | Uso | Dónde queda el scrape |
| --- | --- | --- |
| **Selenium + Chrome** | Extraer perfiles con sesión del asesor | Equipo/servidor de Global; Selenium HQ no recibe el contenido |
| **Firecrawl Cloud** | Sitio de producto y fichas públicas vía API | Infraestructura de Firecrawl (EE. UU.), salvo self-host |

Puntos operativos:

- “Público en internet” **no basta** por sí solo: hace falta autorización o base legal.
- Quien usa IA de terceros (LLM, Firecrawl) sigue siendo responsable del tratamiento.
- Los hechos se aprueban con revisión humana real.
- Extraer en local **no** gasta créditos de Firecrawl; la API sí (Free: 1.000 créditos/mes orientativos).
- Selenium no entrena modelos con el scrape local. En Firecrawl no hay confirmación pública inequívoca de “sí/no entrenan”; ZDR es Enterprise.

### Documentos del proyecto

| Documento | Contenido |
| --- | --- |
| [docs/cumplimiento/guia.md](docs/cumplimiento/guia.md) | Cómo aplica al motor |
| [docs/cumplimiento/proveedores-extraccion.pdf](docs/cumplimiento/proveedores-extraccion.pdf) | PDF principal (privacidad, retención, costos, enlaces) |
| [docs/cumplimiento/fuentes-oficiales.pdf](docs/cumplimiento/fuentes-oficiales.pdf) | Revisión con fuentes oficiales |
| [docs/cumplimiento/enlaces.md](docs/cumplimiento/enlaces.md) | Lista de URLs oficiales |

### Enlaces oficiales (resumen)

- Selenium docs: https://www.selenium.dev/documentation/
- Privacidad ASF: https://privacy.apache.org/policies/privacy-policy-public.html
- Firecrawl privacidad: https://www.firecrawl.dev/privacy-policy
- Firecrawl términos: https://www.firecrawl.dev/terms-of-service
- Firecrawl precios/créditos: https://www.firecrawl.dev/pricing
- Firecrawl seguridad / ZDR: https://docs.firecrawl.dev/security
- Firecrawl Trust Center: https://trust.firecrawl.dev/

La lista completa está en [docs/cumplimiento/enlaces.md](docs/cumplimiento/enlaces.md) y en los PDF.

## Variables de entorno

Ver `.env.example`. Resumen:

| Variable | Uso |
| --- | --- |
| `DATABASE_URL` | Postgres/Neon (si está definida, tiene prioridad) |
| `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Postgres local |
| `DEMO_CLAVE` | Si existe, la pantalla de entrada la pide |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | Modelo en la nube |
| `OLLAMA_*`, `EMBED_MODEL` | Modelo local |
| `FIRECRAWL_API_KEY`, `SITIO_DOMINIO` | Ingesta del sitio de producto |
| `SCRAPE_HEADLESS`, `SCRAPE_MANUAL_LOGIN` | En contenedor: headless y sin login manual |

El archivo `.env` no se sube al repositorio.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

## Seguridad

- No subir `.env`, cookies ni perfiles de Chrome.
- No versionar listados reales de personas autorizadas con datos sensibles si la política interna lo prohíbe.
- En Vercel, sin cookies vigentes las redes suelen bloquear el datacenter: la extracción con login se hace en local (http://127.0.0.1:8000).
