// Arranque: inicio de sesión, estructura (menú según el rol), estado de servicios y enrutador por #hash.
import { del, get, post, sesion } from "./api.js";
import { estado, puede } from "./estado.js";
import { alerta, conBoton, errorCaja, h, icono, toast } from "./ui.js";

const VISTAS = [
  { id: "panel", texto: "Panel", icono: "grid", permiso: "contar", cargar: () => import("./vistas/panel.js") },
  { id: "asistente", texto: "Asistente", icono: "chat", permiso: "contar", cargar: () => import("./vistas/asistente.js") },
  { id: "segmentos", texto: "Segmentos", icono: "layers", permiso: "contar", cargar: () => import("./vistas/segmentos.js") },
  { id: "clientes", texto: "Clientes", icono: "users", permiso: "listar", cargar: () => import("./vistas/clientes.js") },
  { id: "borradores", texto: "Borradores", icono: "mail", permiso: "ver_mensajes", cargar: () => import("./vistas/borradores.js") },
  { id: "conocimiento", texto: "Conocimiento", icono: "book", permiso: "admin_conocimiento", cargar: () => import("./vistas/conocimiento.js") },
  { id: "perfiles", texto: "Perfiles públicos", icono: "idcard", permiso: "admin_perfiles", cargar: () => import("./vistas/perfiles.js?v=20261103d") },
  { id: "mensajes-prueba", texto: "Mensajes de prueba", icono: "whatsapp", permiso: "admin_perfiles", cargar: () => import("./vistas/mensajes_prueba.js") },
  { id: "duplicados", texto: "Duplicados", icono: "merge", permiso: "admin_clientes", cargar: () => import("./vistas/duplicados.js") },
  { id: "auditoria", texto: "Auditoría", icono: "shield", permiso: "ver_auditoria", cargar: () => import("./vistas/auditoria.js") },
];

const ROLES = [
  { id: "analista", titulo: "Analista", texto: "Cifras agregadas, resúmenes y plantillas por segmento. Los grupos pequeños se ocultan (k-anonimato)." },
  { id: "asesor", titulo: "Asesor", texto: "Además: buscar clientes y generar, revisar y aprobar borradores de WhatsApp y correo." },
  { id: "admin", titulo: "Administrador", texto: "Además: revisión del conocimiento, perfiles públicos, publicaciones de LinkedIn, duplicados, ingesta y auditoría." },
];

const raiz = document.getElementById("raiz");
let contenido = null;
let tituloEl = null;

// ------------------------------------------------------------------ estado de servicios
function pill(texto, ok, detalle) {
  return h("span", { class: `pill ${ok === true ? "ok" : ok === "medio" ? "medio" : "mal"}`, title: detalle }, h("span", { class: "punto" }), texto);
}

async function servicios(contenedor) {
  try {
    const e = await get("/api/estado");
    const ollamaOk = e.ollama.ok ? (e.ollama.modelo_ok && e.ollama.embed_ok ? true : "medio") : false;
    const ollamaDet = e.ollama.ok
      ? `Modelo ${e.ollama.modelo}: ${e.ollama.modelo_ok ? "listo" : "NO descargado"} · Embeddings ${e.ollama.embed}: ${e.ollama.embed_ok ? "listo" : "NO descargado (la búsqueda vectorial cae al conocimiento completo)"}`
      : "Ollama no responde en localhost:11434: el asistente y los borradores no funcionarán.";
    contenedor.replaceChildren(
      pill("Base de datos", e.bd.ok, e.bd.ok ? "PostgreSQL conectado" : `Sin conexión: ${e.bd.detalle || ""}`),
      pill("Ollama", ollamaOk, ollamaDet),
      pill("Firecrawl", e.firecrawl.ok ? true : "medio", e.firecrawl.ok ? `Clave configurada · sitio ${e.firecrawl.sitio || "sin SITIO_DOMINIO"}` : "Sin FIRECRAWL_API_KEY: la ingesta web y de perfiles no funcionará."));
    return e;
  } catch {
    contenedor.replaceChildren(pill("Servidor", false, "No responde"));
    return null;
  }
}

// ------------------------------------------------------------------ inicio de sesión
function pantallaIngreso() {
  let rol = "asesor";
  let recordado = "";
  try { recordado = localStorage.getItem("motor_usuario") || ""; } catch { /* sin almacenamiento */ }
    const usuario = h("input", { type: "text", placeholder: "Tu usuario (queda en la auditoría)", value: recordado, autocomplete: "username" });
    const clave = h("input", { type: "password", placeholder: "Clave de acceso (si el servidor la pide)", autocomplete: "current-password" });
    const campoClave = h("div", { class: "campo", hidden: true }, h("span", {}, "Clave"), clave);
    const roles = h("div", { class: "roles" });
  const pintarRoles = () => roles.replaceChildren(...ROLES.map((r) => h("label", { class: `rol ${r.id === rol ? "activo" : ""}` },
    h("input", { type: "radio", name: "rol", checked: r.id === rol, onchange: () => { rol = r.id; pintarRoles(); } }),
    h("div", {}, h("strong", {}, r.titulo), h("span", { class: "muted pequeño" }, r.texto)))));
  pintarRoles();
  const estadoServ = h("div", { class: "servicios" });
  const boton = h("button", { class: "btn btn-primario", type: "submit", style: { width: "100%", padding: "10px" } }, "Ingresar");
  const form = h("form", { class: "card pila", onsubmit: async (ev) => {
    ev.preventDefault();
    const u = usuario.value.trim();
    if (u.length < 2) { toast("Escribe tu usuario.", "error"); usuario.focus(); return; }
    const s = await conBoton(boton, () => post("/api/sesion", { usuario: u, rol, clave: clave.value }));
    if (!s) return;
    try { localStorage.setItem("motor_usuario", u); } catch { /* sin almacenamiento */ }
    sesion.set(s);
    estado.sesion = s;
    if (!location.hash) location.hash = "#/panel";
    montarApp();
  } },
  h("div", { class: "campo" }, h("span", {}, "Usuario"), usuario),
  campoClave,
  h("div", { class: "campo" }, h("span", {}, "Rol"), roles),
  boton,
  h("div", { class: "fila" }, h("span", { class: "muted pequeño" }, "Servicios:"), estadoServ));

  raiz.replaceChildren(h("div", { class: "login" }, h("div", { class: "login-caja" },
    h("div", { class: "login-marca" }, h("div", { class: "logo" }, icono("sparkle")),
      h("div", {}, h("h1", {}, "Motor de Perfilamiento IA"), h("p", { class: "muted" }, "Segmentación, borradores personalizados y gobierno de datos"))),
    form,
    h("p", { class: "muted pequeño", style: { marginTop: "12px", textAlign: "center" } },
      "Herramienta interna. Cada consulta queda registrada en la auditoría con tu usuario y rol."))));
  servicios(estadoServ).then((e) => {
    if (e && e.pide_clave) campoClave.hidden = false;
  });
  usuario.focus();
}

// ------------------------------------------------------------------ estructura principal
function montarApp() {
  const s = estado.sesion;
  const visibles = VISTAS.filter((v) => puede(v.permiso));
  const nav = h("nav", { class: "nav" }, visibles.map((v) => h("a", { href: `#/${v.id}`, "data-vista": v.id }, icono(v.icono), v.texto)));
  const estadoServ = h("div", { class: "servicios fila" });
  tituloEl = h("div", { class: "titulo" });
  contenido = h("main", { class: "contenido", id: "contenido" });
  const app = h("div", { class: "app" },
    h("aside", { class: "lateral" },
      h("div", { class: "marca" }, h("div", { class: "logo" }, icono("sparkle")), h("div", {}, h("strong", {}, "Perfilamiento IA"), h("small", {}, "Global Seguros"))),
      nav,
      h("div", { class: "usuario" },
        h("div", { class: "avatar-u" }, s.usuario.slice(0, 2)),
        h("div", { class: "datos" }, h("div", { class: "recortar" }, s.usuario), h("small", {}, s.rol)),
        h("button", { class: "btn btn-fantasma btn-icono", title: "Cerrar sesión", onclick: cerrarSesion }, icono("logout")))),
    h("div", { class: "principal" },
      h("header", { class: "barra-sup" },
        h("button", { class: "btn btn-fantasma btn-icono menu-movil", title: "Menú", onclick: () => app.classList.toggle("menu-abierto") }, icono("menu")),
        tituloEl,
        h("div", { class: "fila", title: "Estado de los servicios (clic para actualizar)", onclick: () => servicios(estadoServ) }, estadoServ)),
      contenido));
  nav.addEventListener("click", () => app.classList.remove("menu-abierto"));
  raiz.replaceChildren(app);
  servicios(estadoServ);
  clearInterval(intervaloServicios);
  intervaloServicios = setInterval(() => servicios(estadoServ), 60000);
  enrutar();
}
let intervaloServicios = null;

async function cerrarSesion() {
  try { await del("/api/sesion"); } catch { /* da igual: se limpia localmente */ }
  sesion.limpiar();
  estado.sesion = null;
  estado.opciones = null;
  estado.catalogo = null;
  clearInterval(intervaloServicios);
  history.replaceState(null, "", location.pathname);
  pantallaIngreso();
}

// ------------------------------------------------------------------ enrutador
let limpiezaActual = null;
let navegacion = 0;

async function enrutar() {
  if (!estado.sesion || !contenido) return;
  const visibles = VISTAS.filter((v) => puede(v.permiso));
  const id = (location.hash.match(/^#\/([\w-]+)/) || [])[1];
  const vista = visibles.find((v) => v.id === id) || visibles[0];
  if (!vista) { contenido.replaceChildren(alerta("Tu rol no tiene vistas disponibles.", "warn")); return; }
  if (vista.id !== id) { history.replaceState(null, "", `#/${vista.id}`); }
  document.querySelectorAll(".nav a").forEach((a) => a.classList.toggle("activo", a.dataset.vista === vista.id));
  tituloEl.textContent = vista.texto;
  document.title = `${vista.texto} · Motor de Perfilamiento IA`;
  if (typeof limpiezaActual === "function") limpiezaActual();
  limpiezaActual = null;
  const turno = ++navegacion;
  const cont = h("div", { class: "vista" });
  contenido.replaceChildren(cont);
  contenido.scrollTop = 0;
  try {
    const modulo = await vista.cargar();
    if (turno !== navegacion) return;
    limpiezaActual = await modulo.render(cont);
  } catch (e) {
    if (turno === navegacion) cont.replaceChildren(errorCaja(e, enrutar));
  }
}

window.addEventListener("hashchange", enrutar);
window.addEventListener("sesion-vencida", () => {
  if (!estado.sesion) return;            // al arrancar con un token viejo no hace falta avisar
  toast("Tu sesión venció (el servidor se reinició). Ingresa de nuevo.", "info");
  estado.sesion = null;
  clearInterval(intervaloServicios);
  pantallaIngreso();
});

// ------------------------------------------------------------------ arranque
(async () => {
  const guardada = sesion.get();
  if (guardada && guardada.token) {
    try {
      const s = await get("/api/sesion");
      estado.sesion = { ...guardada, ...s };
      montarApp();
      return;
    } catch { sesion.limpiar(); }
  }
  pantallaIngreso();
})();
