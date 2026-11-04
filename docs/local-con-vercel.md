# Ejecutar el motor en local junto a Vercel

La aplicación web ya está desplegada. El scraping de LinkedIn, X, Facebook e Instagram **no puede hacerse en Vercel** (hace falta Chrome con una sesión real). Este documento indica qué instalar y ejecutar en un computador para extraer perfiles autorizados y guardar los hechos en la misma base que usa Vercel.

- Aplicación: https://motor-perfilamiento-ia.vercel.app
- Repositorio: https://github.com/dalvareza009/motor-perfilamiento-ia

## Qué corre en cada lado

| Vercel | Computador local |
| --- | --- |
| Panel, clientes, asistente, borradores, conocimiento | Scraping con Google Chrome |
| PostgreSQL (Neon) | Escritura a esa misma `DATABASE_URL` |
| Modelo (AI Gateway) | Chrome + inicio de sesión en la red social |

Tras un scrape local, los hechos aparecen en la URL de Vercel.

## Requisitos en el computador

1. **Python 3.12 o superior** — https://www.python.org/downloads/  
   Marcar *Add python.exe to PATH*.
2. **Google Chrome** (no Microsoft Edge) — https://www.google.com/chrome/
3. Este repositorio:

```powershell
git clone https://github.com/dalvareza009/motor-perfilamiento-ia.git
cd motor-perfilamiento-ia
```

No es necesario instalar PostgreSQL ni Ollama: la base es Neon y el modelo es el de Vercel.

## Archivo `.env`

```powershell
copy .env.example .env
```

Dejar el `.env` con estas claves (valores en Vercel → proyecto *motor-perfilamiento-ia* → Settings → Environment Variables):

```env
DATABASE_URL=
DEMO_CLAVE=jefe-prueba-2026
SESION_SECRETA=jefe-prueba-2026
LLM_BASE_URL=https://ai-gateway.vercel.sh/v1
LLM_MODEL=openai/gpt-4o-mini
LLM_API_KEY=
```

- `DATABASE_URL`: copiar **DATABASE_URL_UNPOOLED** de Neon (conexión directa). Para extracciones cortas también sirve `DATABASE_URL` (pooler).
- `LLM_API_KEY`: clave de AI Gateway. Sin ella se guardan hechos, pero no se generan recomendaciones ni borradores en local.
- No definir `SCRAPE_HEADLESS=1` ni `SCRAPE_MANUAL_LOGIN=0`: Chrome debe quedar visible para iniciar sesión.

No compartir ni subir a git el `.env`, los JSON de cookies ni las carpetas `chrome_*_profile`.

## Instalar y arrancar

En PowerShell, dentro de la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.api
```

Abrir Google Chrome en http://127.0.0.1:8000

- Usuario: cualquier identificador (queda en auditoría)
- Clave: `jefe-prueba-2026`
- Rol: **Administrador**

## Extraer un perfil autorizado

1. Menú → **Perfiles públicos**.
2. Pegar la URL de un perfil que esté en la lista de autorizados.
3. **Extraer actividad y recomendar**.
4. En la ventana de Chrome, iniciar sesión en esa red (incluido 2FA si aplica).
5. Cuando cargue el feed, volver a http://127.0.0.1:8000 y confirmar que la sesión está activa.

Los hechos se persisten en Neon. Verificarlos en https://motor-perfilamiento-ia.vercel.app con la misma clave y rol Administrador o Asesor.

## Checklist

- [ ] Python 3.12+ en el PATH
- [ ] Google Chrome instalado
- [ ] Repositorio en el disco
- [ ] `.env` con `DATABASE_URL` de Neon
- [ ] `.env` con `DEMO_CLAVE`; `LLM_API_KEY` si se necesitan borradores
- [ ] Dependencias instaladas en `.venv`
- [ ] Servidor en http://127.0.0.1:8000
