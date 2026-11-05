// Seguimiento de una tarea en segundo plano (lote de borradores, scraping): progreso + registro en vivo.
import { get, post } from "./api.js";
import { badge, errorCaja, h } from "./ui.js";

export function seguirTarea(tarea, { alTerminar, titulo } = {}) {
  let desde = 0;
  const relleno = h("span", { class: "progreso-relleno" });
  const progreso = h("div", { class: "progreso indeterminado" }, relleno);
  const estadoEl = h("span", {}, badge("En curso", "info"));
  const contador = h("span", { class: "muted pequeño" });
  const bDetener = h("button", { class: "btn btn-sm btn-peligro-suave" }, "Detener");
  bDetener.addEventListener("click", async () => {
    bDetener.disabled = true;
    await post(`/api/tareas/${tarea.id}/cancelar`, {}).catch(() => {});
  });
  const consola = h("pre", { class: "consola" });
  const detalles = h("details", {}, h("summary", {}, "Ver registro"), consola);
  const resultado = h("div", { class: "pila" });
  const el = h("div", { class: "tarea card" },
    h("div", { class: "tarea-cab" },
      h("div", {}, h("strong", {}, titulo || tarea.descripcion), " ", contador),
      estadoEl, bDetener),
    progreso, detalles, resultado);

  async function tick() {
    let t;
    try {
      t = await get(`/api/tareas/${tarea.id}?desde=${desde}`);
    } catch (e) {
      estadoEl.replaceChildren(badge("Sin conexión", "warn"));
      if (/No existe esa tarea/.test(e.message)) { resultado.replaceChildren(errorCaja(e)); return; }
      setTimeout(tick, 4000);
      return;
    }
    if (t.lineas.length) {
      const abajo = consola.scrollTop + consola.clientHeight >= consola.scrollHeight - 8;
      consola.textContent += `${t.lineas.join("\n")}\n`;
      if (abajo) consola.scrollTop = consola.scrollHeight;
    }
    desde = t.n_lineas;
    if (t.total) {
      progreso.classList.remove("indeterminado");
      relleno.style.width = `${Math.round((100 * t.actual) / t.total)}%`;
      contador.textContent = `${t.actual} de ${t.total}`;
    }
    if (t.estado === "en_curso") { setTimeout(tick, 1500); return; }
    bDetener.remove();
    progreso.classList.remove("indeterminado");
    relleno.style.width = "100%";
    const segundos = t.fin && t.inicio ? Math.round(t.fin - t.inicio) : null;
    if (t.estado === "terminada") {
      estadoEl.replaceChildren(badge(`Terminada${segundos != null ? ` · ${segundos} s` : ""}`, "ok"));
      if (alTerminar) alTerminar(t.resultado, resultado, t);
    } else if (t.estado === "cancelada") {
      estadoEl.replaceChildren(badge("Detenida", "warn"));
    } else {
      estadoEl.replaceChildren(badge("Error", "peligro"));
      resultado.replaceChildren(errorCaja(new Error(t.error || "La tarea falló.")));
      detalles.open = true;
    }
  }
  setTimeout(tick, 400);
  return el;
}
