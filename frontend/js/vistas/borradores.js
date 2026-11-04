// Borradores: bandeja de revisión por estado, detalle con acciones y generación en lote.
import { get } from "../api.js";
import { abrirLote, tareaLote, tarjetaMensaje } from "../componentes.js";
import { puede } from "../estado.js";
import { ESTADOS, badgeEstado, cabecera, canalTexto, cargando, errorCaja, fecha, h, icono, pestañas, tabla, vacio } from "../ui.js";

let estadoActivo = "";

export async function render(cont) {
  let seleccionado = null;
  const zonaTareas = h("div", { class: "pila" });
  const lista = h("div", {}, cargando());
  const detalle = h("div", { class: "detalle" }, h("div", { class: "card" }, vacio("Elige un borrador para revisarlo.", "mail")));
  const items = () => [{ id: "", texto: "Todos" }, ...Object.entries(ESTADOS).map(([id, e]) => ({ id, texto: e.texto }))];
  const tabs = pestañas(items(), estadoActivo, (id) => { estadoActivo = id; cargar(); });

  async function cargar() {
    lista.replaceChildren(cargando());
    try {
      const r = await get(`/api/mensajes?estado=${encodeURIComponent(estadoActivo)}`);
      const total = Object.values(r.conteo).reduce((a, n) => a + n, 0);
      tabs.actualizar(items().map((it) => ({ ...it, n: it.id ? r.conteo[it.id] || 0 : total })));
      lista.replaceChildren(tabla([
        { titulo: "#", valor: (m) => m.id_mensaje, clase: "num" },
        { titulo: "Cliente", valor: (m) => m.nombre || "—" },
        { titulo: "Canal", valor: (m) => h("span", { class: "fila", style: { gap: "4px" } }, icono(m.canal === "whatsapp" ? "whatsapp" : "mail"), canalTexto(m.canal)) },
        { titulo: "Producto", valor: (m) => m.producto || "—" },
        { titulo: "Estado", valor: (m) => badgeEstado(m.estado) },
        { titulo: "Creado", valor: (m) => fecha(m.fecha_creacion) },
      ], r.filas, {
        onFila: (m) => abrir(m.id_mensaje),
        seleccion: (m) => m.id_mensaje === seleccionado,
        vacioTexto: estadoActivo ? `No hay borradores en estado «${ESTADOS[estadoActivo].texto}».` : "Aún no hay borradores. Genéralos desde el Asistente, Clientes o en lote.",
      }));
    } catch (e) {
      lista.replaceChildren(errorCaja(e, cargar));
    }
  }

  async function abrir(id) {
    seleccionado = id;
    lista.querySelectorAll("tbody tr").forEach((tr) => tr.classList.toggle("sel", tr.firstChild.textContent === String(id)));
    detalle.replaceChildren(h("div", { class: "card" }, cargando()));
    try {
      const m = await get(`/api/mensajes/${id}`);
      detalle.replaceChildren(tarjetaMensaje(m, { onCambio: () => cargar() }));
    } catch (e) {
      detalle.replaceChildren(errorCaja(e, () => abrir(id)));
    }
  }

  const bLote = puede("mensajes_lote") ? h("button", { class: "btn btn-primario" }, icono("play"), "Generar en lote") : null;
  if (bLote) bLote.addEventListener("click", () => abrirLote({}, { alLanzar: (t) => zonaTareas.prepend(tareaLote(t, { onCambio: cargar })) }));

  cont.append(
    cabecera("Borradores", "Revisa, aprueba y marca como enviados. Nada se envía desde aquí: copia el texto aprobado a tu canal.",
      h("button", { class: "btn", onclick: () => cargar() }, icono("refresh"), "Actualizar"), bLote),
    zonaTareas,
    h("div", { class: "card pila", style: { padding: "0 0 12px" } },
      h("div", { style: { padding: "4px 12px 0" } }, tabs.el),
      h("div", { class: "dividido", style: { padding: "0 12px" } }, lista, detalle)));

  // Si había lotes en curso (por ejemplo, lanzados desde otra vista), se siguen mostrando aquí.
  try {
    const tareas = await get("/api/tareas");
    for (const t of tareas.filter((x) => x.tipo === "lote" && x.estado === "en_curso")) {
      zonaTareas.append(tareaLote(t, { onCambio: cargar }));
    }
  } catch { /* no es crítico */ }
  cargar();
}
