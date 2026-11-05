# Instalar el motor de perfilamiento en otro computador

Copia este paquete a un PC Windows y deja el motor igual que en el de origen: panel, segmentos, clientes, asistente, borradores, conocimiento, perfiles públicos, scraping con Chrome (Facebook, Instagram, LinkedIn y X), revisión de hechos, contenido, seguidores e intereses.

No incluye `.env`, cookies ni sesiones de Chrome. Esas hay que crearlas en el equipo nuevo.

---

## Qué hay que tener instalado

1. **Python 3.12 o superior** — https://www.python.org/downloads/  
   Marca *Add python.exe to PATH*.
2. **Google Chrome** (no Edge) — https://www.google.com/chrome/
3. **Git** (opcional) — https://git-scm.com/download/win
4. **Ollama** (opcional, solo si el modelo va a correr en este PC) — https://ollama.com/download
5. **PostgreSQL 15–18** (solo si NO vas a usar Neon y quieres la base entera en este PC) — https://www.postgresql.org/download/windows/

Comprobar en PowerShell:

```powershell
python --version
```

---

## Paso 1 — Descomprimir

Descomprime `motor_perfilamiento_ia_equipo.zip` en una carpeta estable, por ejemplo:

`C:\Users\TU_USUARIO\Documents\motor_perfilamiento_ia`

No lo dejes dentro de Descargas. Entra a esa carpeta en el Explorador.

---

## Paso 2 — Archivo `.env`

En la raíz del proyecto:

```powershell
copy .env.example .env
```

Abre `.env` y elige **una** de las dos formas.

### Forma A — Igual que el PC de origen (recomendado)

El scraping corre aquí con Chrome; la base y el modelo son los de Neon / Vercel.

Pega los mismos valores que en el otro computador (Vercel → Settings → Environment Variables, o el `.env` de origen):

```env
DATABASE_URL=
DEMO_CLAVE=jefe-prueba-2026
SESION_SECRETA=jefe-prueba-2026
LLM_BASE_URL=https://ai-gateway.vercel.sh/v1
LLM_MODEL=openai/gpt-4o-mini
LLM_API_KEY=
```

- `DATABASE_URL`: en Neon usa **DATABASE_URL_UNPOOLED**.
- No pongas `SCRAPE_HEADLESS=1`: Chrome tiene que verse para iniciar sesión.

### Forma B — Todo en este PC (sin Neon)

Comenta `DATABASE_URL` y deja:

```env
# DATABASE_URL=
DB_HOST=localhost
DB_PORT=5432
DB_NAME=base_datos
DB_USER=postgres
DB_PASSWORD=la_clave_de_tu_postgres
DEMO_CLAVE=jefe-prueba-2026
SESION_SECRETA=jefe-prueba-2026
OLLAMA_URL=http://localhost:11434/api/chat
OLLAMA_MODEL=qwen3:4b-instruct
OLLAMA_EMBED_URL=http://localhost:11434/api/embed
EMBED_MODEL=nomic-embed-text
```

PostgreSQL tiene que estar instalado y el servicio en ejecución.

---

## Paso 3 — Preparar el equipo

Doble clic en `INSTALAR.bat`, o en PowerShell dentro de la carpeta:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\preparar-equipo.ps1
```

Eso crea `.venv`, instala `requirements.txt` y, si usas la forma B, carga `datos_iniciales/base_datos.sql`.

---

## Paso 4 — Arrancar

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\iniciar.ps1
```

Deja esa ventana abierta. En **Google Chrome** entra a http://127.0.0.1:8000

| Campo | Valor |
| --- | --- |
| Usuario | el que quieras (queda en auditoría) |
| Clave | `jefe-prueba-2026` (o la de `DEMO_CLAVE`) |
| Rol | **Administrador** |

---

## Paso 5 — Scraping (primera vez en este PC)

Las sesiones de Facebook, Instagram, LinkedIn y X **no viajan** en el zip. En este computador hay que entrar otra vez:

1. Menú → **Perfiles públicos**.
2. Pega una URL o usa Extraer lote / Página Facebook.
3. Chrome se abre: inicia sesión en esa red (2FA si aplica).
4. Cuando veas el feed, confirma en la web del motor.

A partir de ahí las cookies quedan en este PC (`*_cookies.json` y `chrome_*_profile/`). No las copies a git ni a otro zip.

El botón Extraer de vercel.app **no** abre el Chrome de este PC. Extrae siempre desde http://127.0.0.1:8000.

---

## Qué hace el motor (todo incluido)

- Panel, segmentos, clientes, asistente, borradores, conocimiento, duplicados, auditoría.
- Perfiles públicos: personas autorizadas, lote de URLs, perfiles generales, páginas de seguros (MAPFRE y otras).
- Scraping con sesión propia: ficha, publicaciones (texto completo, «ver más»), familia etiquetada, bios y captions, seguidores e intereses, otra red ligada.
- Revisión de hechos, revisión de contenido, seguidores e intereses.
- Los hechos se escriben aunque la URL no esté en Personas autorizadas.

---

## Si algo falla

| Síntoma | Qué hacer |
| --- | --- |
| `python` no se reconoce | Reinstala Python marcando PATH; cierra y abre PowerShell |
| Error de base / timeout | Forma A: `DATABASE_URL` UNPOOLED e internet. Forma B: servicio PostgreSQL y `DB_PASSWORD` |
| Extraer en vercel.app no abre Chrome | Extrae en http://127.0.0.1:8000 |
| La red pide login | Completa el login en la ventana de Chrome de **este** PC; usa Chrome, no Edge |
| Sin recomendaciones ni borradores | Falta `LLM_API_KEY` (forma A) o Ollama con `qwen3:4b-instruct` (forma B) |

---

## Qué no va en este paquete (a propósito)

- `.env` y claves
- `linkedin_cookies.json`, `facebook_cookies.json`, `instagram_cookies.json`, `x_cookies.json`
- Carpetas `chrome_*_profile`
- `data/perfiles_autorizados.json` de otro equipo (aquí va el ejemplo)

En el equipo nuevo se crea `data/perfiles_autorizados.json` a partir de `data/perfiles_autorizados.ejemplo.json`.
