# Motor de perfilamiento IA

Herramienta interna de Global Seguros: segmentación de clientes, borradores de WhatsApp y correo, conocimiento de producto y lectura de **perfiles públicos autorizados** (LinkedIn, X, Facebook, Instagram, Substack y Reddit).

Las cifras salen de SQL. El modelo solo interpreta preguntas y redacta textos; no inventa coberturas ni datos personales. Cada consulta queda en auditoría.

- Código: https://github.com/dalvareza009/motor-perfilamiento-ia
- App en Vercel: https://motor-perfilamiento-ia.vercel.app

## Qué incluye

- **Panel y segmentos:** conteos, k-anonimato para el rol analista, plantillas por grupo.
- **Clientes:** ficha, hechos de perfil, perfil IA, borradores por canal.
- **Asistente:** pregunta en lenguaje natural → intención (LLM) → SQL o generación de mensajes (código).
- **Borradores:** validación automática, estados (borrador → revisión → aprobado → enviado).
- **Conocimiento:** ingesta del sitio (Firecrawl), aprobación humana, búsqueda vectorial si hay embeddings.
- **Perfiles públicos:** lista de personas que autorizaron por escrito; scraping con la sesión de Chrome de quien opera (incluye Substack y Reddit).
- **Duplicados y auditoría.**
- **Tratamiento de datos:** documentación de Selenium y Firecrawl (privacidad, retención, créditos).

### Roles

| Rol | Alcance |
| --- | --- |
| Analista | Cifras agregadas, resúmenes y plantillas. Los grupos con menos de 5 personas se ocultan. |
| Asesor | Lo anterior más fichas, borradores individuales y en lote. |
| Administrador | Lo anterior más conocimiento, perfiles, duplicados, ingesta y auditoría. |

## Cómo está armado

```
frontend/     Interfaz (HTML/JS)
app/          API FastAPI y reglas de negocio
*_scraper.py  LinkedIn, X, Facebook, Instagram, Substack, Reddit (Selenium + Chrome)
docs/         Tratamiento de datos y diagramas
data/         Perfiles autorizados
tests/        Pruebas
scripts/      Arranque local y carga de base
```

- **Datos:** PostgreSQL (`DATABASE_URL` o `DB_HOST` / `DB_NAME` locales). En Vercel se usa Neon.
- **Modelo:** Ollama en local (`qwen3:4b-instruct`) o API compatible (`LLM_BASE_URL`, en Vercel AI Gateway).
- **Scraping:** Google Chrome en el PC. En Vercel no hay login manual; sin cookies vigentes las redes bloquean el datacenter.

Para instalarlo en **otro computador**: descomprime `motor_perfilamiento_ia_equipo.zip` y sigue la guía **[INSTALAR.md](INSTALAR.md)** (o ejecuta `INSTALAR.bat`). Las claves (`DB_PASSWORD`, Firecrawl, opcionalmente Neon/LLM) se pasan aparte, no van en el zip.

## Arranque 100 % local

Instalar Python 3.12+, Google Chrome, PostgreSQL 18 y Ollama (`qwen3:4b-instruct`, `nomic-embed-text`).

```powershell
copy .env.example .env
# En .env: comenta DATABASE_URL y LLM_*; descomenta DB_* y OLLAMA_*
# Ajusta DB_PASSWORD a la de tu Postgres

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\scripts\restaurar-base.ps1          # si tienes datos_iniciales/base_datos.sql
.\.venv\Scripts\python.exe -m app.api
```

O: `scripts\preparar-equipo.ps1` y luego `scripts\iniciar.ps1`.

Abrir http://127.0.0.1:8000 — usuario a elección, clave vacía si no hay `DEMO_CLAVE`, rol Administrador.

## Scraping

Solo perfiles en `data/perfiles_autorizados.json` con autorización marcada.

1. Rol administrador → **Perfiles públicos**.
2. Pegar la URL (LinkedIn, X, Facebook, Instagram, Substack o Reddit).
3. Extraer. Chrome se abre: iniciar sesión en esa red y confirmar en la web.
4. Los hechos quedan pendientes de revisión; los aprobados se usan en borradores.

En todas las redes se revisa, si está dicho o se ve: a quién sigue, intereses de vida, publicaciones y reposts útiles para acercarnos, estado civil, hijos, escolaridad, empresa, dónde estudió y el rango salarial solo si la persona lo publica (para el asesor; no va al mensaje al cliente).

No versionar `*.json` de cookies ni carpetas `chrome_*_profile`.

## Tratamiento de datos (Selenium y Firecrawl)

El motor usa dos vías distintas para obtener contenido web:

| Vía | Para qué | Dónde viven los datos del scrape |
| --- | --- | --- |
| **Selenium + Chrome** | Extraer perfiles con sesión del asesor | En el equipo / servidor de Global; Selenium HQ no recibe el contenido |
| **Firecrawl Cloud** | Ingesta del sitio de producto y fichas públicas vía API | Pasan por la infraestructura de Firecrawl (EE. UU.), salvo self-host |

Resumen operativo: un dato “público” no basta por sí solo; hace falta autorización o base legal. Los hechos se aprueban con revisión humana. Extraer en local no gasta créditos de Firecrawl.

Documentación completa (privacidad, retención, entrenamiento, ZDR, precios/créditos y enlaces oficiales):

- Guía del proyecto: [docs/tratamiento_datos_selenium_firecrawl.md](docs/tratamiento_datos_selenium_firecrawl.md)
- PDF principal: [docs/Selenium_Firecrawl_Tratamiento_Datos.pdf](docs/Selenium_Firecrawl_Tratamiento_Datos.pdf)
- Revisión adicional con fuentes: [docs/Revision_politicas_tratamiento_datos_Selenium_y_Firecrawl.pdf](docs/Revision_politicas_tratamiento_datos_Selenium_y_Firecrawl.pdf)

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

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
