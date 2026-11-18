# Tratamiento de datos: Selenium y Firecrawl

Documento de referencia para el motor de perfilamiento IA de Global Seguros.

## Documento principal

- **PDF:** [Selenium_Firecrawl_Tratamiento_Datos.pdf](./Selenium_Firecrawl_Tratamiento_Datos.pdf)

Revisa privacidad, retención, entrenamiento de modelos, seguridad, costos/créditos y enlaces oficiales de ambas herramientas. Incluye notas de Ley 1581 de 2012 y Decreto 1074 de 2015 (Colombia).

## Cómo aplica a este proyecto

| Herramienta | Uso en el motor | Lectura clave del PDF |
| --- | --- | --- |
| **Selenium + Chrome** | Extraer perfiles en redes (LinkedIn, Facebook, Instagram, X, Substack, Reddit) con sesión local | El contenido no se envía a Selenium HQ; la retención y seguridad las define Global (PC, cookies, Postgres). No hay entrenamiento de IA por parte de Selenium. |
| **Firecrawl Cloud** | Ingesta del sitio de producto y, cuando aplica, fichas públicas vía API (`FIRECRAWL_API_KEY`) | Las URL y el contenido pasan por Firecrawl (EE. UU.). Hay caché; ZDR es Enterprise. No hay confirmación pública inequívoca de “sí/no entrenan” con cada scrape: para datos personales conviene confirmación contractual. |
| **LLM (API u Ollama)** | Asistente y borradores | Queda fuera del PDF; Global sigue siendo responsable del tratamiento cuando usa IA de terceros. |

Reglas operativas que el PDF refuerza y el código ya asume:

1. Autorización / base legal antes de leer un perfil (no basta con que sea “público”).
2. Hechos pendientes de revisión humana real antes de usarlos en borradores.
3. No versionar cookies ni perfiles de Chrome.
4. Extraer en local no consume créditos de Firecrawl; la API sí.

## Documento relacionado

- [Revision_politicas_tratamiento_datos_Selenium_y_Firecrawl.pdf](./Revision_politicas_tratamiento_datos_Selenium_y_Firecrawl.pdf) — revisión previa con el mismo criterio (fuentes oficiales).

## Nota

El PDF no sustituye un dictamen jurídico ni un DPA firmado. Tarifas y políticas pueden cambiar; verificar los enlaces oficiales citados en el documento.
