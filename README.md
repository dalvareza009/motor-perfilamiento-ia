# Qué ejecutar en local para usar la solución con Vercel

La interfaz ya está en Vercel. **El scraping no puede correr ahí** (Chrome, login y cookies de redes). Para que el jefe vea hechos nuevos en la nube, hay que scrapear en un PC y escribir en la **misma base Neon** que usa Vercel.

- App: https://motor-perfilamiento-ia.vercel.app
- Código: https://github.com/dalvareza009/motor-perfilamiento-ia

## 1. Qué hace falta en el PC

| Software | Para qué | Enlace |
| --- | --- | --- |
| Python 3.12 o superior | Correr la app y los scrapers | https://www.python.org/downloads/ (marca *Add python.exe to PATH*) |
| Google Chrome (no Edge) | Sesión de LinkedIn / X / Facebook / Instagram | https://www.google.com/chrome/ |
| Git (opcional) | Clonar el repo | ya instalado en el equipo de desarrollo |
| Este repositorio | Código del motor | `git clone https://github.com/dalvareza009/motor-perfilamiento-ia.git` |

**No hace falta** instalar Postgres ni Ollama en el PC: la base es Neon y el modelo es el AI Gateway de Vercel.

## 2. Variables de entorno (conectar local → Vercel)

En la raíz del proyecto:

```powershell
copy .env.example .env
```

Edita `.env` y deja **solo** esto (valores desde Vercel → proyecto *motor-perfilamiento-ia* → Settings → Environment Variables):

```env
DATABASE_URL=
DEMO_CLAVE=jefe-prueba-2026
SESION_SECRETA=jefe-prueba-2026
LLM_BASE_URL=https://ai-gateway.vercel.sh/v1
LLM_MODEL=openai/gpt-4o-mini
LLM_API_KEY=
```

Cómo rellenar:

- `DATABASE_URL`: copia **DATABASE_URL_UNPOOLED** (conexión directa de Neon). Si el scrape es corto, sirve `DATABASE_URL` (pooler).
- `LLM_API_KEY`: clave de AI Gateway (Vercel → AI). Sin esto el scrape guarda hechos, pero no arma recomendaciones/borradores en local.
- No pongas `SCRAPE_HEADLESS=1` ni `SCRAPE_MANUAL_LOGIN=0`: en el PC Chrome debe verse para que inicies sesión.

No subas `.env` a GitHub. Tampoco cookies ni carpetas `chrome_*_profile`.

## 3. Instalar dependencias y arrancar

PowerShell, dentro de la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.api
```

Abre **Google Chrome** en http://127.0.0.1:8000

- Usuario: el que quieras (auditoría)
- Clave: `jefe-prueba-2026`
- Rol: **Administrador**

## 4. Scrapear (esto es lo que Vercel no puede hacer)

1. Menú → **Perfiles públicos**.
2. URL de un perfil **autorizado** (LinkedIn, X, Facebook o Instagram).
3. **Extraer actividad y recomendar**.
4. En la ventana de Chrome que se abre, entra con **tu** cuenta de esa red (2FA si pide).
5. Cuando veas el feed, vuelve a http://127.0.0.1:8000 y confirma que ya iniciaste sesión.

Los hechos se guardan en Neon. El resto del equipo los ve en https://motor-perfilamiento-ia.vercel.app (misma clave y rol Administrador o Asesor).

## 5. Checklist rápido

- [ ] Python 3.12+ en PATH
- [ ] Google Chrome instalado
- [ ] Repo clonado o carpeta del proyecto
- [ ] `.env` con `DATABASE_URL` de Neon (la de Vercel)
- [ ] `.env` con `DEMO_CLAVE` y, si quieres borradores, `LLM_API_KEY`
- [ ] `pip install -r requirements.txt` en `.venv`
- [ ] `python -m app.api` y Chrome en el puerto 8000

## Modo 100 % local (sin Vercel ni Neon)

Si no vas a usar la nube: instala PostgreSQL 18 y Ollama (`qwen3:4b-instruct`, `nomic-embed-text`). Sigue `PARA_EL_JEFE.txt` y `scripts\preparar-equipo.ps1`. En ese caso el `.env` usa `DB_HOST` / `DB_PASSWORD` y **no** lleva `DATABASE_URL`.
