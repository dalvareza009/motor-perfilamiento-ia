# Motor de perfilamiento IA

La app web está en **Vercel**. El scraping de redes (LinkedIn, X, Facebook, Instagram) **no corre ahí**: hay que ejecutarlo en un PC con Google Chrome. Este README lista lo que ese equipo local necesita para alimentar la misma solución que ya está desplegada.

App en Vercel: https://motor-perfilamiento-ia.vercel.app

## Qué corre dónde

| En Vercel (nube) | En el PC (local) |
| --- | --- |
| Panel, clientes, hechos, conocimiento, asistente, borradores | Scraping con Chrome de tu sesión |
| Postgres en Neon (`DATABASE_URL`) | El scrape escribe en **esa misma** Neon |
| Modelo (AI Gateway), si la tarjeta de Vercel está activa | Chrome + cookies / login manual |

Si scrapeas en local apuntando a Neon, el jefe ve los hechos nuevos en el enlace de Vercel sin instalar nada.

## Qué instalar en el PC

1. **Python 3.12 o superior** — https://www.python.org/downloads/  
   En el instalador marca *Add python.exe to PATH*.
2. **Google Chrome** (no Edge) — https://www.google.com/chrome/
3. Este repositorio (carpeta del proyecto).

No hace falta Postgres ni Ollama en el PC si usas Neon y el modelo de Vercel.

## Configurar el `.env` local (para ir con Vercel)

En la raíz del proyecto:

```bat
copy .env.example .env
```

Deja el `.env` así (pega los valores desde Vercel → Project → Settings → Environment Variables):

```env
DATABASE_URL=<connection string de Neon, la misma de Vercel>
DEMO_CLAVE=jefe-prueba-2026
SESION_SECRETA=jefe-prueba-2026
LLM_BASE_URL=https://ai-gateway.vercel.sh/v1
LLM_MODEL=openai/gpt-4o-mini
LLM_API_KEY=<clave de AI Gateway en Vercel>
```

Usa la URL **unpooled** / `DATABASE_URL_UNPOOLED` de Neon si el scrape es largo.

No subas el `.env` ni las cookies (`x_cookies.json`, `linkedin_cookies.json`, carpetas `chrome_*_profile`).

## Arrancar en local (solo para scrapear)

En PowerShell, dentro de la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.api
```

Abre Chrome en http://127.0.0.1:8000

- Usuario: el que quieras (queda en auditoría)
- Clave: `jefe-prueba-2026` (la misma de Vercel)
- Rol: **Administrador**

## Cómo scrapear

1. Menú → **Perfiles públicos**.
2. Pega la URL de un perfil **autorizado** (LinkedIn, X, Facebook o Instagram).
3. **Extraer actividad y recomendar**.
4. Se abre Chrome: entra con **tu** cuenta de esa red (2FA si lo pide).
5. Cuando veas el feed, vuelve a la web local y confirma que ya iniciaste sesión.

Los hechos quedan en Neon. Compruébalos en https://motor-perfilamiento-ia.vercel.app

## Si no quieres Vercel (todo en el PC)

Instala además PostgreSQL 18 y Ollama (`qwen3:4b-instruct` y `nomic-embed-text`).  
Pasos: `PARA_EL_JEFE.txt`, `scripts\preparar-equipo.ps1` y `scripts\iniciar.ps1`.  
En ese modo el `.env` usa `DB_HOST` / `DB_PASSWORD` locales, no `DATABASE_URL`.
