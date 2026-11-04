// Segmentos: define un grupo con filtros, cuéntalo, resúmelo y redacta una plantilla de mensaje.
import { post } from "../api.js";
import { abrirLote, tareaLote, tarjetaConteo, tarjetaPlantilla, tarjetaResumen } from "../componentes.js";
import { catalogo, irA, opciones, puede, tomarPreset } from "../estado.js";
import { constructorFiltros } from "../filtros.js";
import { cabecera, campo, cargando, chipsFiltros, conBoton, errorCaja, etiqueta, h, icono, poner, selector, vacio } from "../ui.js";

export async function render(cont) {
  const preset = tomarPreset();
  const [ops, cat] = await Promise.all([opciones(), catalogo()]);

  let filtros = constructorFiltros({ opciones: ops, iniciales: preset, alEnter: () => analizar() });
  const zonaFiltros = h("div", {}, filtros.el);
  const agrupar = selector(cat.dimensiones.map((d) => ({ valor: d, texto: etiqueta(d) })), "segmento");
  const resultados = h("div", { class: "pila" }, vacio("Define un grupo (o déjalo vacío para toda la base) y pulsa «Analizar».", "layers"));
  const zonaPlantilla = h("div", { class: "pila" });
  const zonaTareas = h("div", { class: "pila" });

  const bAnalizar = h("button", { class: "btn btn-primario" }, icono("search"), "Analizar");
  const bLimpiar = h("button", { class: "btn btn-fantasma" }, "Limpiar");
  const bPlantilla = puede("mensaje_segmento") ? h("button", { class: "btn" }, icono("sparkle"), "Plantilla de mensaje") : null;
  const bClientes = puede("listar") ? h("button", { class: "btn" }, icono("users"), "Ver clientes") : null;
  const bLote = puede("mensajes_lote") ? h("button", { class: "btn" }, icono("mail"), "Borradores en lote") : null;

  async function analizar() {
    const f = filtros.valores();
    const dim = agrupar.value;
    resultados.replaceChildren(cargando("Consultando…"));
    try {
      const [conteo, resumen] = await Promise.all([
        post("/api/contar", { filtros: f, agrupar_por: dim }),
        puede("resumen") ? post("/api/resumen", { filtros: f }) : null,
      ]);
      poner(resultados,
        h("div", { class: "fila" }, h("span", { class: "muted" }, "Grupo:"), chipsFiltros(f)),
        resumen ? h("div", { class: "card" }, tarjetaResumen(resumen.resumen)) : null,
        h("div", { class: "card" }, tarjetaConteo(conteo, {
          onValor: (fila) => {
            if (fila.valor === "sin_dato") return;
            const nuevos = { ...f, [dim]: fila.valor };
            filtros = constructorFiltros({ opciones: ops, iniciales: nuevos, alEnter: () => analizar() });
            zonaFiltros.replaceChildren(filtros.el);
            analizar();
          },
        })));
    } catch (e) {
      resultados.replaceChildren(errorCaja(e, analizar));
    }
  }

  bAnalizar.addEventListener("click", analizar);
  bLimpiar.addEventListener("click", () => { filtros.limpiar(); });
  if (bPlantilla) {
    bPlantilla.addEventListener("click", async () => {
      zonaPlantilla.replaceChildren(h("div", { class: "card" }, cargando("Redactando con el modelo local y validando… (hasta 3 intentos)")));
      const r = await conBoton(bPlantilla, () => post("/api/plantilla", { filtros: filtros.valores() }));
      zonaPlantilla.replaceChildren(r ? h("div", { class: "card" }, tarjetaPlantilla(r)) : "");
    });
  }
  if (bClientes) bClientes.addEventListener("click", () => irA("clientes", filtros.valores()));
  if (bLote) {
    bLote.addEventListener("click", () => abrirLote(filtros.valores(), {
      alLanzar: (t) => zonaTareas.prepend(tareaLote(t)),
    }));
  }

  cont.append(
    cabecera("Segmentos", "Explora grupos de clientes. Las cifras salen de SQL y respetan los permisos de tu rol."),
    h("div", { class: "card pila" },
      h("div", { class: "card-cab", style: { marginBottom: 0 } }, icono("filter"), h("h2", {}, "Grupo de clientes")),
      zonaFiltros,
      h("div", { class: "fila", style: { alignItems: "flex-end" } },
        h("div", { style: { width: "220px" } }, campo("Agrupar el conteo por", agrupar)),
        h("span", { class: "espaciador" }),
        bLimpiar, bClientes, bLote, bPlantilla, bAnalizar)),
    zonaTareas, zonaPlantilla, resultados);

  if (Object.keys(preset).length) analizar();
}
