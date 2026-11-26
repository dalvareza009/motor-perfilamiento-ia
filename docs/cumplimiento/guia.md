# Cumplimiento: proveedores de extracción

Referencia para el motor de perfilamiento IA de Global Seguros.

## Documentos

- **PDF principal:** [proveedores-extraccion.pdf](./proveedores-extraccion.pdf)
- **Revisión de fuentes oficiales:** [fuentes-oficiales.pdf](./fuentes-oficiales.pdf)
- **Enlaces oficiales:** [enlaces.md](./enlaces.md)

Cubren privacidad, retención, entrenamiento de modelos, seguridad, costos, créditos, enlaces oficiales y en qué momento el motor usa cada herramienta.

## Cómo aplica a este proyecto

| Herramienta | Uso en el motor | Lectura clave |
| --- | --- | --- |
| **Selenium + Chrome** | Extraer perfiles en redes con sesión local | El contenido no se envía a Selenium HQ; la retención y seguridad las define Global (PC, cookies, Postgres). No hay entrenamiento de IA por parte de Selenium. |
| **Firecrawl Cloud** | Sitio de producto y lote de perfiles autorizados (`FIRECRAWL_API_KEY`). No es el botón Extraer. | Las URL y el contenido pasan por Firecrawl (EE. UU.). No hay un interruptor general para impedir entrenamiento. ZDR es Enterprise. |
| **LLM (API u Ollama)** | Asistente y borradores | Queda fuera de estos PDF; Global sigue siendo responsable del tratamiento cuando usa IA de terceros. |

Reglas operativas que el código ya asume:

1. Autorización / base legal antes de leer un perfil (no basta con que sea “público”).
2. Hechos pendientes de revisión humana real antes de usarlos en borradores.
3. No versionar cookies ni perfiles de Chrome.
4. Extraer en local no consume créditos de Firecrawl; la API sí.

## Nota

Estos documentos no sustituyen un dictamen jurídico ni un DPA firmado. Tarifas y políticas pueden cambiar; verificar los enlaces oficiales citados en los PDF.
