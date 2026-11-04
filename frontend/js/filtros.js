// Constructor de filtros sobre las dimensiones permitidas (misma lista blanca que segmentos.DIMENSIONES).
import { campo, etiqueta, h, selector } from "./ui.js";

export const CATEGORICAS = ["producto_interes", "segmento", "rango_edad", "genero"];
export const TEXTO = ["ciudad", "profesion", "universidad"];
export const BOOLEANAS = ["tiene_correo", "tiene_celular", "tiene_universidad"];
export const TODAS = [...CATEGORICAS, ...TEXTO, ...BOOLEANAS];

let secuencia = 0;

function aSiNo(v) {
  if (v === true || v === "true" || v === "si" || v === "sí") return "si";
  if (v === false || v === "false" || v === "no") return "no";
  return "";
}

export function constructorFiltros({ opciones = {}, iniciales = {}, dims = TODAS, alEnter } = {}) {
  const controles = {};
  const grid = h("div", { class: "filtros-grid" });
  for (const dim of dims) {
    const inicial = iniciales[dim];
    let control;
    if (BOOLEANAS.includes(dim)) {
      control = selector([{ valor: "", texto: "Cualquiera" }, { valor: "si", texto: "Sí" }, { valor: "no", texto: "No" }], aSiNo(inicial));
    } else if (CATEGORICAS.includes(dim)) {
      const valores = [...(opciones[dim] || [])];
      if (inicial && !valores.includes(String(inicial))) valores.unshift(String(inicial));
      control = selector([{ valor: "", texto: "Todos" }, ...valores.map((v) => ({ valor: v, texto: v }))], inicial ?? "");
    } else {
      const id = `dl-${dim}-${++secuencia}`;
      control = h("input", { type: "text", list: id, placeholder: "Contiene…", value: inicial ?? "" });
      grid.append(h("datalist", { id }, (opciones[dim] || []).map((v) => h("option", { value: v }))));
      if (alEnter) control.addEventListener("keydown", (e) => { if (e.key === "Enter") alEnter(); });
    }
    controles[dim] = control;
    grid.append(campo(etiqueta(dim), control));
  }
  return {
    el: grid,
    valores() {
      const out = {};
      for (const [d, c] of Object.entries(controles)) {
        const v = c.value.trim();
        if (v) out[d] = v;
      }
      return out;
    },
    limpiar() { for (const c of Object.values(controles)) c.value = ""; },
  };
}
