# Ejecutar el motor en local junto a Vercel

Guía para levantar la solución **en este computador**, extraer perfiles autorizados con Google Chrome y guardar los hechos en la misma base que usa Vercel.

- Aplicación: https://motor-perfilamiento-ia.vercel.app
- Repositorio: https://github.com/dalvareza009/motor-perfilamiento-ia

El scraping de LinkedIn, X, Facebook e Instagram no corre en Vercel: hace falta Chrome con una sesión real. Este PC es el que abre el navegador. Vercel sigue sirviendo el panel, Neon la base y AI Gateway el modelo (salvo que se active el paso opcional de Ollama).

| En Vercel | En este PC |
| --- | --- |
| Panel, clientes, asistente, borradores, conocimiento | Scraping con Google Chrome |
| PostgreSQL (Neon) | Escritura a esa misma `DATABASE_URL` |
| Modelo (AI Gateway) | Chrome + inicio de sesión en la red social |

No hace falta instalar PostgreSQL. Ollama y el túnel son opcionales.

No compartir ni subir a git el `.env`, los JSON de cookies ni las carpetas `chrome_*_profile`.

---

## Paso 1 — Instalar programas

1. **Python 3.12 o superior** — https://www.python.org/downloads/  
   En el instalador, marcar *Add python.exe to PATH*.
2. **Google Chrome** (no Microsoft Edge) — https://www.google.com/chrome/
3. **Git** — https://git-scm.com/download/win
4. **Cloudflare Tunnel** (`cloudflared`), solo si se va a publicar una URL `https://` hacia este PC:  
   https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/  
   o en PowerShell:

   ```powershell
   winget install --id Cloudflare.cloudflared
   ```

5. **Ollama**, solo si este PC va a servir el modelo a Vercel: https://ollama.com/download

Comprobar:

```powershell
python --version
git --version
```

---

## Paso 2 — Copiar valores desde Vercel y Neon

En Vercel: proyecto **motor-perfilamiento-ia** → **Settings** → **Environment Variables**.

| Variable | Dónde tomarla | Uso |
| --- | --- | --- |
| `DATABASE_URL` | Neon: **DATABASE_URL_UNPOOLED** (conexión directa). Para pruebas cortas también sirve `DATABASE_URL` (pooler). | Base compartida con Vercel |
| `DEMO_CLAVE` | Ya definida: `jefe-prueba-2026` | Entrada a la web |
| `SESION_SECRETA` | Misma que en Vercel, o `jefe-prueba-2026` | Sesión firmada |
| `LLM_API_KEY` | Vercel AI Gateway | Recomendaciones y borradores en este PC |
| `LLM_BASE_URL` | `https://ai-gateway.vercel.sh/v1` | Dejar así salvo el paso 7 |
| `LLM_MODEL` | `openai/gpt-4o-mini` | Dejar así salvo el paso 7 |

Hace falta permiso de lectura (y de edición si se hace el paso 7) sobre ese proyecto Vercel.

---

## Paso 3 — Clonar el repositorio

```powershell
git clone https://github.com/dalvareza009/motor-perfilamiento-ia.git
cd motor-perfilamiento-ia
```

---

## Paso 4 — Crear el archivo `.env`

```powershell
copy .env.example .env
```

Editar `.env` y dejarlo así (pegar los secretos copiados en el paso 2):

```env
DATABASE_URL=
DEMO_CLAVE=jefe-prueba-2026
SESION_SECRETA=jefe-prueba-2026
LLM_BASE_URL=https://ai-gateway.vercel.sh/v1
LLM_MODEL=openai/gpt-4o-mini
LLM_API_KEY=
```

- No definir `SCRAPE_HEADLESS=1` ni `SCRAPE_MANUAL_LOGIN=0`: Chrome debe quedar visible para iniciar sesión.
- Sin `LLM_API_KEY` se guardan hechos, pero no se generan recomendaciones ni borradores en local.

---

## Paso 5 — Instalar dependencias y arrancar

En PowerShell, dentro de `motor-perfilamiento-ia`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.api
```

Dejar esa ventana abierta. Abrir **Google Chrome** en http://127.0.0.1:8000

- Usuario: cualquier identificador (queda en auditoría)
- Clave: `jefe-prueba-2026`
- Rol: **Administrador**

---

## Paso 6 — Extraer un perfil autorizado

1. Menú → **Perfiles públicos**.
2. Pegar la URL de un perfil que esté en la lista de autorizados.
3. **Extraer actividad y recomendar**.
4. En la ventana de Chrome que se abre, iniciar sesión en esa red (incluido 2FA si aplica).
5. Cuando cargue el feed, volver a http://127.0.0.1:8000 y confirmar que la sesión está activa.

Los hechos se escriben en Neon. Comprobarlos en https://motor-perfilamiento-ia.vercel.app con la misma clave y rol Administrador o Asesor.

El botón **Extraer** de vercel.app no abre el Chrome de este PC. La extracción se lanza desde http://127.0.0.1:8000 (o desde la URL del túnel del paso 8).

---

## Paso 7 — Opcional: que Vercel use Ollama de este PC

Solo el asistente y los borradores de **vercel.app**. El scraping sigue siendo local (paso 6).

1. Instalar Ollama y, en una terminal:

   ```powershell
   ollama pull qwen3:4b-instruct
   ```

2. Exponer Ollama en todas las interfaces. Cerrar Ollama si está en bandeja y, en PowerShell:

   ```powershell
   $env:OLLAMA_HOST = "0.0.0.0:11434"
   ollama serve
   ```

3. En **otra** terminal:

   ```powershell
   cloudflared tunnel --url http://127.0.0.1:11434
   ```

4. Copiar la URL `https://….trycloudflare.com`.
5. En Vercel → **motor-perfilamiento-ia** → **Settings** → **Environment Variables** (Production):

   | Variable | Valor |
   | --- | --- |
   | `LLM_BASE_URL` | `https://SU-TUNEL.trycloudflare.com/v1` |
   | `LLM_MODEL` | `qwen3:4b-instruct` |
   | `LLM_API_KEY` | `ollama` |

6. **Redeploy** del proyecto. Probar el asistente en vercel.app con este PC encendido y `cloudflared` + `ollama serve` abiertos.

Si se apaga el PC, se duerme o se cierra el túnel, el asistente en Vercel deja de responder.

Al terminar la prueba, restaurar en Vercel:

```env
LLM_BASE_URL=https://ai-gateway.vercel.sh/v1
LLM_MODEL=openai/gpt-4o-mini
LLM_API_KEY=<clave de AI Gateway>
```

y volver a desplegar.

---

## Paso 8 — Opcional: túnel del motor (entrar desde otra red)

Publica http://127.0.0.1:8000 con HTTPS. El scrape sigue ejecutándose **en este escritorio**.

1. Completar los pasos 1 a 5. Tiene que responder http://127.0.0.1:8000.
2. En **otra** ventana de PowerShell:

   ```powershell
   cloudflared tunnel --url http://127.0.0.1:8000
   ```

3. Abrir en Chrome la URL `https://….trycloudflare.com` que imprime el comando.
4. Entrar con la misma clave y rol Administrador. Extraer como en el paso 6: Chrome se abre en **este** PC.

Mantener abiertos el proceso de `app.api` y el de `cloudflared`. No suspender el equipo.

El túnel rápido es público: quien tenga la URL llega a este motor. No dejarlo encendido de forma permanente. Al terminar: Ctrl+C en la ventana de `cloudflared`.

Esto no hace que el botón Extraer de vercel.app use este Chrome.

---

## Checklist

- [ ] Python 3.12+ y Git en el PATH
- [ ] Google Chrome instalado
- [ ] Repositorio clonado
- [ ] `.env` con `DATABASE_URL` de Neon (UNPOOLED)
- [ ] `.env` con `DEMO_CLAVE`; `LLM_API_KEY` si se necesitan borradores
- [ ] Dependencias instaladas en `.venv`
- [ ] Servidor en http://127.0.0.1:8000
- [ ] Extracción hecha desde este PC y hechos visibles en vercel.app
- [ ] (Opcional) `cloudflared` para el motor o para Ollama
- [ ] (Opcional) Variables de Vercel restauradas a AI Gateway al cerrar la prueba de Ollama

---

## Si algo falla

| Síntoma | Qué revisar |
| --- | --- |
| `python` no se reconoce | Reinstalar Python marcando PATH; cerrar y abrir PowerShell |
| Error de base / timeout | Usar `DATABASE_URL_UNPOOLED`; PC con internet |
| Extraer en vercel.app no abre Chrome aquí | Es el comportamiento actual. Extraer en `127.0.0.1:8000` o en la URL de cloudflared |
| LinkedIn / X piden login o bloquean | Completar el login en la ventana de Chrome de este PC; no usar Edge |
| `cloudflared` no conecta | Probar red de casa o hotspot; no red con proxy TLS corporativo |
| Asistente caído en Vercel tras el paso 7 | PC, Ollama y túnel vivos; o restaurar AI Gateway y redesplegar |
