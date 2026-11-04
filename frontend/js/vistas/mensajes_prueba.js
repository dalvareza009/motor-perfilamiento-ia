// Tres mensajes de prueba por prospecto, después del análisis del perfil.
import { get } from "../api.js";
import { cabecera, cargando, copiar, errorCaja, fecha, h, icono, toast, vacio, badge } from "../ui.js";

function opcion(m) {
  const bCopiar = h("button", { class: "btn btn-sm" }, icono("copy"), "Copiar");
  bCopiar.addEventListener("click", async () => {
    await copiar(m.cuerpo);
    toast("Mensaje copiado.");
  });
  return h("div", { class: "card pila-sm" },
    h("div", { class: "item-cab" },
      h("strong", {}, `Opción ${m.opcion}`),
      badge(m.estado === "borrador" ? "Listo para revisar" : "Revisar", m.estado === "borrador" ? "ok" : "warn"),
      h("span", { class: "espaciador" }),
      bCopiar),
    h("div", { class: "mensaje-cuerpo whatsapp" }, m.cuerpo),
    (m.errores || []).length ? h("div", { class: "muted pequeño" }, m.errores.join(" ")) : null);
}

function prospecto(p) {
  return h("article", { class: "card pila" },
    h("div", { class: "item-cab" },
      h("h3", { style: { margin: "0" } }, p.nombre),
      badge(p.producto, "info"),
      badge(p.red, ""),
      h("span", { class: "espaciador" }),
      h("span", { class: "muted pequeño" }, fecha(p.creado_en))),
    p.fuente_url ? h("a", { href: p.fuente_url, target: "_blank", rel: "noopener noreferrer", class: "pequeño" }, p.fuente_url) : null,
    h("div", { class: "pila" }, (p.opciones || []).map(opcion)));
}

export function vistaMensajes() {
  const zona = h("div", { class: "pila" }, cargando());
  cargar(zona);
  return zona;
}

async function cargar(zona) {
  zona.replaceChildren(cargando());
  try {
    const filas = await get("/api/mensajes-prueba");
    zona.replaceChildren(filas.length
      ? h("div", { class: "pila" }, filas.map(prospecto))
      : vacio("Todavía no hay mensajes. Lee un perfil autorizado y, si el análisis sugiere un producto, aquí aparecen tres opciones.", "whatsapp"));
  } catch (e) {
    zona.replaceChildren(errorCaja(e, () => cargar(zona)));
  }
}

export async function render(cont) {
  cont.append(
    cabecera("Mensajes de prueba", "Tres opciones por prospecto, redactadas al analizar su perfil. Son borradores: no se envían y hay que revisarlos antes de usarlos."),
    vistaMensajes());
}
