# Motor de perfilamiento IA

Herramienta interna de Global Seguros: segmentación de clientes, borradores de WhatsApp y correo, conocimiento de producto y lectura de **perfiles públicos autorizados** (LinkedIn, X, Facebook, Instagram).

Las cifras salen de SQL. El modelo solo interpreta preguntas y redacta textos; no inventa coberturas ni datos personales. Cada consulta queda en auditoría.

- Código: https://github.com/dalvareza009/motor-perfilamiento-ia
- App en Vercel: https://motor-perfilamiento-ia.vercel.app

## Qué incluye

- **Panel y segmentos:** conteos, k-anonimato para el rol analista, plantillas por grupo.
- **Clientes:** ficha, hechos de perfil, perfil IA, borradores por canal.
- **Asistente:** pregunta en lenguaje natural → intención (LLM) → SQL o generación de mensajes (código).
- **Borradores:** validación automática, estados (borrador → revisión → aprobado → enviado).
- **Conocimiento:** ingesta del sitio (Firecrawl), aprobación humana, búsqueda vectorial si hay embeddings.
- **Perfiles públicos:** lista de personas que autorizaron por escrito; scraping con la sesión de Chrome de quien opera.
- **Duplicados y auditoría.**

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
*_scraper.py  LinkedIn, X, Facebook, Instagram (Selenium + Chrome)
data/         Perfiles autorizados
tests/        Pruebas
scripts/      Arranque local y carga de base
```

- **Datos:** PostgreSQL (`DATABASE_URL` o `DB_HOST` / `DB_NAME` locales). En Vercel se usa Neon.
- **Modelo:** Ollama en local (`qwen3:4b-instruct`) o API compatible (`LLM_BASE_URL`, en Vercel AI Gateway).
- **Scraping:** Google Chrome en el PC. En Vercel no hay login manual; sin cookies vigentes las redes bloquean el datacenter.

Hay dos formas de correrlo:

1. **Local + Vercel** (scraping en el PC, app y base en la nube): [ejecucion-local-vercel.md](ejecucion-local-vercel.md)
2. **Todo en el PC** (Postgres y Ollama propios): sección siguiente.

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
2. Pegar la URL (LinkedIn, X, Facebook o Instagram).
3. Extraer. Chrome se abre: iniciar sesión en esa red y confirmar en la web.
4. Los hechos quedan pendientes de revisión; los aprobados se usan en borradores.

No versionar `*.json` de cookies ni carpetas `chrome_*_profile`.

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
