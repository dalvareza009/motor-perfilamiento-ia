// Utilidades de interfaz sin dependencias. Todo dato entra como texto (textContent), nunca como HTML:
// el contenido scrapeado o generado por el modelo no puede inyectar marcado.

export function h(tag, attrs, ...hijos) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k === "value") el.value = v;
    else if (k === "checked" || k === "disabled" || k === "selected" || k === "open") el[k] = Boolean(v);
    else if (v === true) el.setAttribute(k, "");
    else el.setAttribute(k, v);
  }
  agregar(el, hijos);
  return el;
}

function agregar(el, hijos) {
  for (const c of hijos.flat(Infinity)) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
}

/** Como el.replaceChildren(), pero ignora null/false igual que h() (el nativo escribiría "null"). */
export function poner(el, ...hijos) {
  el.replaceChildren();
  agregar(el, hijos);
  return el;
}

// ------------------------------------------------------------------ iconos (marcado constante)
const ICONOS = {
  grid: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
  chat: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  layers: '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
  users: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  user: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  mail: '<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>',
  whatsapp: '<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>',
  book: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
  idcard: '<path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><polyline points="17 11 19 13 23 9"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
  send: '<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>',
  copy: '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  check: '<polyline points="20 6 9 17 4 12"/>',
  x: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
  refresh: '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>',
  play: '<polygon points="5 3 19 12 5 21 5 3"/>',
  plus: '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
  trash: '<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
  search: '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
  external: '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>',
  alert: '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
  info: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
  sparkle: '<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
  database: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
  filter: '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
  globe: '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
  menu: '<line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/>',
  save: '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>',
  eye: '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
  merge: '<circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M6 21V9a9 9 0 0 0 9 9"/>',
  split: '<polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/>',
};

export function icono(nombre, clase = "") {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", `ico ${clase}`.trim());
  svg.setAttribute("aria-hidden", "true");
  svg.innerHTML = ICONOS[nombre] || "";
  return svg;
}

// ------------------------------------------------------------------ formato
const nf = new Intl.NumberFormat("es-CO");
export const num = (n) => (n == null || n === "" ? "—" : nf.format(Number(n)));
export const pct = (n, total) => (total ? `${Math.round((100 * n) / total)}%` : "—");

export function fecha(v) {
  if (v == null || v === "") return "—";
  // Una fecha sin hora ("2026-08-31") se lee como medianoche UTC: en Colombia mostraría el día anterior.
  const soloDia = typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v);
  if (soloDia) {
    const [a, m, d] = v.split("-").map(Number);
    return new Date(a, m - 1, d).toLocaleDateString("es-CO", { dateStyle: "medium" });
  }
  const d = typeof v === "number" ? new Date(v * 1000) : new Date(v);
  return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });
}

export const ETIQUETAS = {
  segmento: "Segmento", rango_edad: "Rango de edad", ciudad: "Ciudad", profesion: "Profesión",
  universidad: "Universidad", producto_interes: "Producto de interés", genero: "Género",
  tiene_universidad: "Tiene universidad", tiene_correo: "Tiene correo", tiene_celular: "Tiene celular",
};
export const etiqueta = (dim) => ETIQUETAS[dim] || dim;

export function legible(v) {
  if (v === true || v === "true" || v === "si") return "Sí";
  if (v === false || v === "false" || v === "no") return "No";
  if (v == null || v === "" || v === "sin_dato") return "Sin dato";
  return String(v);
}

export const ACCIONES = {
  contar: "Contar", listar: "Listar clientes", resumen: "Resumen", mensaje_segmento: "Plantilla de mensaje",
  mensaje_cliente: "Borrador para un cliente", mensajes_lote: "Borradores en lote",
};

export const ESTADOS = {
  borrador: { texto: "Borrador", clase: "info" },
  requiere_revision: { texto: "Requiere revisión", clase: "warn" },
  aprobado: { texto: "Aprobado", clase: "ok" },
  enviado: { texto: "Enviado", clase: "primario" },
  descartado: { texto: "Descartado", clase: "" },
};

export const canalTexto = (c) => (c === "whatsapp" ? "WhatsApp" : c === "correo" ? "Correo" : c || "—");

// ------------------------------------------------------------------ piezas
export const badge = (texto, clase = "") => h("span", { class: `badge ${clase ? `badge-${clase}` : ""}` }, texto);
export function badgeEstado(e) {
  const d = ESTADOS[e] || { texto: e, clase: "" };
  return badge(d.texto, d.clase);
}

export function alerta(contenido, tipo = "info") {
  const ico = { info: "info", warn: "alert", peligro: "alert", ok: "check" }[tipo] || "info";
  return h("div", { class: `alerta alerta-${tipo}` }, icono(ico), h("div", {}, contenido));
}

export const vacio = (texto, ico = "info") => h("div", { class: "vacio" }, icono(ico), h("div", {}, texto));
export const cargando = (texto = "Cargando…") => h("div", { class: "cargando" }, h("div", { class: "giro" }), texto);

export function errorCaja(e, reintentar) {
  return alerta([
    h("strong", {}, "No se pudo completar"), h("div", {}, (e && e.message) || String(e || "Error")),
    reintentar ? h("button", { class: "btn btn-sm", style: { marginTop: "8px" }, onclick: reintentar }, icono("refresh"), "Reintentar") : null,
  ], "peligro");
}

export function campo(texto, control, ayuda) {
  return h("label", { class: "campo" }, h("span", {}, texto), control, ayuda ? h("span", { class: "ayuda" }, ayuda) : null);
}

export function selector(opciones, valor = "", attrs = {}) {
  const el = h("select", attrs, opciones.map((o) => {
    const op = typeof o === "object" ? o : { valor: o, texto: o };
    return h("option", { value: op.valor }, op.texto);
  }));
  el.value = valor ?? "";
  return el;
}

export function segmentado(opciones, valor, alCambiar) {
  const el = h("div", { class: "segmentado", role: "group" });
  const pintar = () => el.replaceChildren(...opciones.map((o) => h("button", {
    type: "button", class: o.valor === valor ? "activo" : "",
    onclick: () => { valor = o.valor; pintar(); alCambiar && alCambiar(valor); },
  }, o.icono ? icono(o.icono) : null, o.texto)));
  pintar();
  return el;
}

export function pestañas(items, activa, alCambiar) {
  const el = h("div", { class: "pestañas", role: "tablist" });
  const pintar = () => el.replaceChildren(...items.map((it) => h("button", {
    class: `pestaña ${it.id === activa ? "activa" : ""}`, role: "tab",
    onclick: () => { activa = it.id; pintar(); alCambiar(it.id); },
  }, it.texto, it.n != null ? h("span", { class: "n" }, num(it.n)) : null)));
  pintar();
  return {
    el,
    actualizar(nuevos) { items = nuevos; pintar(); },
    activar(id) { activa = id; pintar(); },
  };
}

export function barras(filas, { onClick, max = 12, total } = {}) {
  const lista = filas.slice(0, max);
  const tope = Math.max(1, ...lista.map((f) => f.n));
  const suma = total || filas.reduce((a, f) => a + f.n, 0);
  return h("div", { class: "barras" }, lista.map((f) => h("div", {
    class: `barra-fila ${onClick ? "clic" : ""}`, title: `${legible(f.valor)}: ${num(f.n)}`,
    onclick: onClick ? () => onClick(f) : null,
  },
  h("span", { class: "barra-etq" }, legible(f.valor)),
  h("span", { class: "barra-pista" }, h("span", { class: "barra-relleno", style: { width: `${(100 * f.n) / tope}%` } })),
  h("span", { class: "barra-n" }, num(f.n), h("small", {}, pct(f.n, suma))))),
  filas.length > max ? h("div", { class: "muted pequeño", style: { padding: "4px 6px" } }, `y ${filas.length - max} más…`) : null);
}

export function tabla(columnas, filas, { onFila, seleccion, vacioTexto = "Sin resultados." } = {}) {
  if (!filas.length) return vacio(vacioTexto);
  return h("div", { class: "tabla-envoltura" }, h("table", {},
    h("thead", {}, h("tr", {}, columnas.map((c) => h("th", { class: c.clase || "" }, c.titulo)))),
    h("tbody", {}, filas.map((f) => h("tr", {
      class: `${onFila ? "clic" : ""} ${seleccion && seleccion(f) ? "sel" : ""}`,
      onclick: onFila ? () => onFila(f) : null,
    }, columnas.map((c) => h("td", { class: c.clase || "" }, c.valor(f))))))));
}

export function chipsFiltros(filtros) {
  const pares = Object.entries(filtros || {});
  if (!pares.length) return h("span", { class: "chip chip-estatico" }, "Todos los clientes");
  return pares.map(([k, v]) => h("span", { class: "chip chip-estatico" }, `${etiqueta(k)}: ${legible(v)}`));
}

// ------------------------------------------------------------------ interacción
export function toast(texto, tipo = "ok", ms = 4500) {
  const ico = tipo === "error" ? "alert" : tipo === "info" ? "info" : "check";
  const t = h("div", { class: `toast toast-${tipo}`, role: "status" }, icono(ico), h("div", {}, texto));
  document.getElementById("toasts").append(t);
  setTimeout(() => { t.classList.add("saliendo"); setTimeout(() => t.remove(), 300); }, ms);
}

/** Desactiva el botón mientras corre fn; muestra el error como toast y devuelve undefined si falla. */
export async function conBoton(boton, fn) {
  if (boton && boton.disabled) return undefined;
  if (boton) { boton.disabled = true; boton.classList.add("cargando"); }
  try {
    return await fn();
  } catch (e) {
    toast(e.message || String(e), "error", 8000);
    return undefined;
  } finally {
    if (boton) { boton.disabled = false; boton.classList.remove("cargando"); }
  }
}

export async function copiar(texto) {
  try {
    await navigator.clipboard.writeText(texto);
  } catch {
    const area = h("textarea", { style: { position: "fixed", opacity: "0" } }, texto);
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
  toast("Copiado al portapapeles.", "info", 2200);
}

function alEscape(fn) {
  const manejador = (e) => { if (e.key === "Escape") fn(); };
  document.addEventListener("keydown", manejador);
  return () => document.removeEventListener("keydown", manejador);
}

export function modal({ titulo, contenido, acciones = [{ texto: "Cerrar" }], alCerrar }) {
  const velo = h("div", { class: "velo modal-velo" });
  const pie = h("div", { class: "modal-pie" });
  const caja = h("div", { class: "modal", role: "dialog", "aria-modal": "true", "aria-label": titulo },
    h("div", { class: "modal-cab" }, h("h2", {}, titulo),
      h("button", { class: "btn btn-fantasma btn-icono", title: "Cerrar", onclick: () => cerrar() }, icono("x"))),
    h("div", { class: "modal-cuerpo" }, contenido), pie);
  let quitarEsc = () => {};
  const cerrar = () => {
    if (!caja.isConnected) return;
    velo.remove(); caja.remove(); quitarEsc();
    if (alCerrar) alCerrar();
  };
  quitarEsc = alEscape(cerrar);
  velo.addEventListener("click", cerrar);
  for (const a of acciones) {
    const b = h("button", { class: `btn ${a.clase || (a.primario ? "btn-primario" : "")}` }, a.icono ? icono(a.icono) : null, a.texto);
    b.addEventListener("click", () => (a.accion ? a.accion(cerrar, b) : cerrar()));
    pie.append(b);
  }
  document.body.append(velo, caja);
  const primero = caja.querySelector("input, textarea, select");
  if (primero) primero.focus();
  return { cerrar, caja };
}

/** Promesa con true/false. Cerrar con Esc o clic fuera cuenta como "no". */
export function confirmar(titulo, texto, { boton = "Confirmar", peligro = false } = {}) {
  return new Promise((resolver) => {
    let respuesta = false;
    modal({
      titulo, contenido: h("p", {}, texto), alCerrar: () => resolver(respuesta),
      acciones: [
        { texto: "Cancelar" },
        { texto: boton, clase: peligro ? "btn-peligro" : "btn-primario", accion: (cerrar) => { respuesta = true; cerrar(); } },
      ],
    });
  });
}

let cajonActual = null;
export function cajon(titulo) {
  if (cajonActual) cajonActual.cerrar();
  const tituloEl = h("h2", { class: "recortar" }, titulo);
  const cuerpo = h("div", { class: "cajon-cuerpo" });
  const velo = h("div", { class: "velo" });
  const el = h("aside", { class: "cajon", role: "dialog", "aria-modal": "true" },
    h("div", { class: "cajon-cab" }, tituloEl,
      h("button", { class: "btn btn-fantasma btn-icono", title: "Cerrar", onclick: () => api.cerrar() }, icono("x"))),
    cuerpo);
  let quitarEsc = () => {};
  const api = {
    cuerpo,
    setTitulo(t) { tituloEl.textContent = t; },
    cerrar() { velo.remove(); el.remove(); quitarEsc(); if (cajonActual === api) cajonActual = null; },
  };
  quitarEsc = alEscape(() => api.cerrar());
  velo.addEventListener("click", () => api.cerrar());
  document.body.append(velo, el);
  cajonActual = api;
  return api;
}

export function cabecera(titulo, descripcion, ...acciones) {
  return h("div", { class: "cab-vista" },
    h("div", {}, h("h1", {}, titulo), descripcion ? h("p", { class: "muted" }, descripcion) : null),
    h("div", { class: "fila" }, acciones));
}
