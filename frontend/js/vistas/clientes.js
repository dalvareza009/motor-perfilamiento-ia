// Clientes: búsqueda por nombre o clave + filtros, y ficha completa en un panel lateral.
import { post } from "../api.js";
import { abrirCliente, tablaClientes } from "../componentes.js";
import { opciones, tomarPreset } from "../estado.js";
import { constructorFiltros } from "../filtros.js";
import { cabecera, cargando, errorCaja, h, icono, num, vacio } from "../ui.js";

const DIMS = ["producto_interes", "segmento", "rango_edad", "genero", "ciudad", "profesion", "universidad", "tiene_correo", "tiene_celular"];

export async function render(cont) {
  const preset = tomarPreset();
  const ops = await opciones();
  const q = h("input", { type: "search", placeholder: "Nombre o clave del cliente…" });
  const filtros = constructorFiltros({ opciones: ops, iniciales: preset, dims: DIMS, alEnter: () => buscar() });
  const masFiltros = h("details", { open: Object.keys(preset).length > 0 }, h("summary", {}, "Filtros"), h("div", { style: { marginTop: "12px" } }, filtros.el));
  const resultados = h("div", {}, vacio("Busca por nombre o clave, o aplica filtros. Se muestran hasta 50 clientes por búsqueda (minimización de datos).", "users"));
  const bBuscar = h("button", { class: "btn btn-primario" }, icono("search"), "Buscar");

  async function buscar() {
    resultados.replaceChildren(cargando("Buscando…"));
    bBuscar.disabled = true;
    try {
      const r = await post("/api/clientes/buscar", { q: q.value.trim(), filtros: filtros.valores() });
      resultados.replaceChildren(h("div", { class: "pila-sm" },
        h("div", { class: "fila" }, h("strong", {}, `${num(r.filas.length)} cliente(s)`),
          r.truncado ? h("span", { class: "muted" }, `· se muestran los primeros ${r.limite}; afina la búsqueda para ver otros`) : null,
          h("span", { class: "muted pequeño" }, "· clic en una fila para abrir la ficha")),
        tablaClientes(r.filas, { onAbrir: (f) => abrirCliente(f.clave_cliente) })));
    } catch (e) {
      resultados.replaceChildren(errorCaja(e, buscar));
    } finally {
      bBuscar.disabled = false;
    }
  }
  q.addEventListener("keydown", (e) => { if (e.key === "Enter") buscar(); });
  bBuscar.addEventListener("click", buscar);
  const bLimpiar = h("button", { class: "btn btn-fantasma", onclick: () => { q.value = ""; filtros.limpiar(); q.focus(); } }, "Limpiar");

  cont.append(
    cabecera("Clientes", "Ficha del cliente, hechos de perfil aprobados, perfil IA y sus borradores."),
    h("div", { class: "card pila" },
      h("div", { class: "fila" }, h("div", { class: "buscador" }, icono("search"), q), bLimpiar, bBuscar),
      masFiltros),
    resultados);
  if (Object.keys(preset).length) buscar();
  else q.focus();
}
