# Cumplimiento: proveedores de extracción

Referencia para el motor de perfilamiento IA de Global Seguros.

## Documentos

- **PDF principal:** [proveedores-extraccion.pdf](./proveedores-extraccion.pdf)
- **Revisión de fuentes oficiales:** [fuentes-oficiales.pdf](./fuentes-oficiales.pdf)

Cubren privacidad, retención, entrenamiento de modelos, seguridad, costos/créditos y enlaces oficiales de Selenium y Firecrawl, con notas de Ley 1581 de 2012 y Decreto 1074 de 2015 (Colombia).

## Cómo aplica a este proyecto

| Herramienta | Uso en el motor | Lectura clave |
| --- | --- | --- |
| **Selenium + Chrome** | Extraer perfiles en redes con sesión local | El contenido no se envía a Selenium HQ; la retención y seguridad las define Global (PC, cookies, Postgres). No hay entrenamiento de IA por parte de Selenium. |
| **Firecrawl Cloud** | Ingesta del sitio de producto y, cuando aplica, fichas públicas vía API (`FIRECRAWL_API_KEY`) | Las URL y el contenido pasan por Firecrawl (EE. UU.). Hay caché; ZDR es Enterprise. No hay confirmación pública inequívoca de “sí/no entrenan” con cada scrape: para datos personales conviene confirmación contractual. |
| **LLM (API u Ollama)** | Asistente y borradores | Queda fuera de estos PDF; Global sigue siendo responsable del tratamiento cuando usa IA de terceros. |

Reglas operativas que el código ya asume:

1. Autorización / base legal antes de leer un perfil (no basta con que sea “público”).
2. Hechos pendientes de revisión humana real antes de usarlos en borradores.
3. No versionar cookies ni perfiles de Chrome.
4. Extraer en local no consume créditos de Firecrawl; la API sí.

## Nota

Estos documentos no sustituyen un dictamen jurídico ni un DPA firmado. Tarifas y políticas pueden cambiar; verificar los enlaces oficiales citados en los PDF.
