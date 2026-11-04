// Auditoría: quién consultó qué, con qué parámetros y con qué resultado (public.auditoria_consultas).
import { get } from "../api.js";
import { badge, cabecera, campo, cargando, errorCaja, fecha, h, icono, num, selector, tabla } from "../ui.js";

function celda(col, valor) {
  if (valor == null) return h("span", { class: "muted" }, "—");
  if (col === "resultado") return badge(String(valor), valor === "ok" ? "ok" : "peligro");
  if (col === "parametros") {
    const texto = typeof valor === "string" ? valor : JSON.stringify(valor, null, 1);
    const corto = texto.replace(/\s+/g, " ");
    return corto.length > 90
      ? h("details", {}, h("summary", { class: "mono" }, `${corto.slice(0, 90)}…`), h("pre", { class: "mono", style: { whiteSpace: "pre-wrap" } }, texto))
      : h("span", { class: "mono" }, corto);
  }
  if (typeof valor === "string" && /^\d{4}-\d{2}-\d{2}T/.test(valor)) return fecha(valor);
  return String(valor);
}

export async function render(cont) {
  const usuario = h("input", { type: "search", placeholder: "Usuario…" });
  const accion = selector([{ valor: "", texto: "Todas las acciones" }], "");
  const limite = selector(["100", "200", "500", "1000"], "200");
  const zona = h("div", {}, cargando());

  async function cargar() {
    zona.replaceChildren(cargando());
    const params = new URLSearchParams({ usuario: usuario.value.trim(), accion: accion.value, limite: limite.value });
    try {
      const r = await get(`/api/auditoria?${params}`);
      const actual = accion.value;
      accion.replaceChildren(h("option", { value: "" }, "Todas las acciones"),
        ...r.acciones.map((a) => h("option", { value: a.accion }, `${a.accion} (${num(a.n)})`)));
      accion.value = actual;
      zona.replaceChildren(h("div", { class: "pila-sm" },
        h("span", { class: "muted" }, `${num(r.filas.length)} registro(s), del más reciente al más antiguo`),
        tabla(r.columnas.map((c) => ({ titulo: c, valor: (f) => celda(c, f[c]), clase: c === "filas" ? "num" : "" })), r.filas,
          { vacioTexto: "Sin registros con esos filtros." })));
    } catch (e) {
      zona.replaceChildren(errorCaja(e, cargar));
    }
  }
  usuario.addEventListener("keydown", (e) => { if (e.key === "Enter") cargar(); });
  accion.addEventListener("change", cargar);
  limite.addEventListener("change", cargar);

  cont.append(
    cabecera("Auditoría", "Cada consulta, generación y cambio de estado queda registrado con usuario, rol y parámetros.",
      h("button", { class: "btn", onclick: cargar }, icono("refresh"), "Actualizar")),
    h("div", { class: "card pila" },
      h("div", { class: "filtros-grid" }, campo("Usuario", usuario), campo("Acción", accion), campo("Registros", limite)),
      zona));
  cargar();
}
