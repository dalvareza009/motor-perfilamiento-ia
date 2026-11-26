# Motor de perfilamiento IA — instalación en otro computador

Guía para dejar el motor igual que en el PC de origen: panel, segmentos, clientes, asistente, borradores, conocimiento, perfiles públicos y scraping con Chrome (Facebook, Instagram, LinkedIn y X).

El zip **no trae** `.env`, cookies ni sesiones de Chrome. Esas se crean aquí.

Paquete: `motor_perfilamiento_ia_equipo.zip`

---

## 1. Programas

Instalar en este PC, en este orden:

| Programa | Enlace | Nota |
| --- | --- | --- |
| Python 3.12 o superior | https://www.python.org/downloads/ | Marcar **Add python.exe to PATH** |
| Google Chrome | https://www.google.com/chrome/ | No usar Edge |
| PostgreSQL 15–18 | https://www.postgresql.org/download/windows/ | Hace falta si la base va a vivir en este PC |
| Ollama (opcional) | https://ollama.com/download | Solo para asistente, recomendaciones y borradores en local |

Si instalan Ollama, en PowerShell:

```powershell
ollama pull qwen3:4b-instruct
ollama pull nomic-embed-text
```

Comprobar Python:

```powershell
python --version
```

---

## 2. Descomprimir

Descomprimir el zip en una carpeta estable, por ejemplo:

`C:\Users\TU_USUARIO\Documents\motor_perfilamiento_ia`

No dejarlo en Descargas. Abrir esa carpeta en el Explorador.

---

## 3. Archivo `.env`

En la raíz del proyecto, en PowerShell:

```powershell
copy .env.example .env
```

Abrir `.env` y dejarlo así (es el modo de este equipo: Postgres local + Firecrawl + Ollama):

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=base_datos
DB_USER=postgres
DB_PASSWORD=
K_MIN=0
SITIO_DOMINIO=globalseguroscolombia.com
FIRECRAWL_API_KEY=
DEMO_CLAVE=jefe-prueba-2026
SESION_SECRETA=jefe-prueba-2026
OLLAMA_URL=http://localhost:11434/api/chat
OLLAMA_MODEL=qwen3:4b-instruct
OLLAMA_EMBED_URL=http://localhost:11434/api/embed
EMBED_MODEL=nomic-embed-text
```

Completar a mano:

- `DB_PASSWORD`: la clave que pusieron al instalar PostgreSQL. Si les pasaron la del equipo de origen, usen esa **solo si** en este PC Postgres tiene la misma clave.
- `FIRECRAWL_API_KEY`: la key de Firecrawl que les pasaron aparte (hace falta para ingestar el sitio de producto).

Entrada a la web:

- Clave: `jefe-prueba-2026`
- Rol: **Administrador**

No poner `SCRAPE_HEADLESS=1`: Chrome tiene que verse para iniciar sesión en las redes.

### Opcional: misma base y modelo de Vercel / Neon

Si van a compartir la base de la nube (no la local), comentar las líneas `DB_*` y `OLLAMA_*` y usar:

```env
DATABASE_URL=
DEMO_CLAVE=jefe-prueba-2026
SESION_SECRETA=jefe-prueba-2026
LLM_BASE_URL=https://ai-gateway.vercel.sh/v1
LLM_MODEL=openai/gpt-4o-mini
LLM_API_KEY=
FIRECRAWL_API_KEY=
SITIO_DOMINIO=globalseguroscolombia.com
```

`DATABASE_URL` y `LLM_API_KEY` salen de Vercel → Settings → Environment Variables. En Neon usar **DATABASE_URL_UNPOOLED**.

---

## 4. Preparar el equipo

Doble clic en `INSTALAR.bat`, o en PowerShell dentro de la carpeta:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\preparar-equipo.ps1
```

Eso crea `.venv`, instala las librerías y, si no hay `DATABASE_URL`, carga `datos_iniciales/base_datos.sql` en Postgres.

---

## 5. Arrancar

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\iniciar.ps1
```

Dejar esa ventana abierta. En **Google Chrome** entrar a http://127.0.0.1:8000

| Campo | Valor |
| --- | --- |
| Usuario | el que quieran (queda en auditoría) |
| Clave | `jefe-prueba-2026` |
| Rol | **Administrador** |

---

## 6. Scraping (primera vez en este PC)

Las sesiones de Facebook, Instagram, LinkedIn y X **no van en el zip**. Hay que entrar otra vez en este computador:

1. Menú → **Perfiles públicos**.
2. Pegar una URL, Extraer lote o Página Facebook.
3. Chrome se abre: iniciar sesión en esa red (2FA si aplica).
4. Cuando cargue el feed, confirmar en la web del motor.

A partir de ahí las cookies quedan en este PC (`*_cookies.json` y `chrome_*_profile/`). No copiarlas a git ni a otro zip.

El botón Extraer de vercel.app **no** abre el Chrome de este PC. Extraer siempre desde http://127.0.0.1:8000.

---

## Qué queda instalado

- Panel, segmentos, clientes, asistente, borradores, conocimiento, duplicados, auditoría.
- Perfiles públicos: personas autorizadas, lote de URLs, perfiles generales, páginas de seguros (MAPFRE y otras).
- Scraping: ficha, publicaciones completas («ver más»), familia etiquetada, bios y captions, seguidores e intereses, nota si hay otra red ligada.
- Revisión de hechos, revisión de contenido, seguidores e intereses.
- Los hechos se guardan aunque la URL no esté en Personas autorizadas.

---

## Si algo falla

| Síntoma | Qué hacer |
| --- | --- |
| `python` no se reconoce | Reinstalar Python marcando PATH; cerrar y abrir PowerShell |
| Error de base | Servicio PostgreSQL en ejecución y `DB_PASSWORD` igual a la de Postgres |
| Extraer en vercel.app no abre Chrome | Extraer en http://127.0.0.1:8000 |
| La red pide login | Completar el login en la ventana de Chrome de **este** PC; usar Chrome, no Edge |
| Sin recomendaciones ni borradores | Instalar Ollama con `qwen3:4b-instruct`, o poner `LLM_API_KEY` de Vercel |
| Sin ingesta del sitio | Falta `FIRECRAWL_API_KEY` |

---

## Qué no va en el zip (a propósito)

- `.env` y claves
- Cookies: `linkedin_cookies.json`, `facebook_cookies.json`, `instagram_cookies.json`, `x_cookies.json`
- Carpetas `chrome_*_profile`
- `data/perfiles_autorizados.json` de otro equipo (aquí se crea desde `data/perfiles_autorizados.ejemplo.json`)
