// Asistente: pregunta en lenguaje natural -> el modelo solo interpreta la intención -> SQL / borradores.
import { post } from "../api.js";
import {
  abrirCliente, diagnostico, resultadoBorrador, tablaClientes, tarjetaConteo, tarjetaMensaje, tarjetaPlantilla,
  tarjetaResumen, tareaLote,
} from "../componentes.js";
import { catalogo, irA, puede } from "../estado.js";
import { ACCIONES, alerta, canalTexto, chipsFiltros, conBoton, etiqueta, h, icono, num, segmentado } from "../ui.js";

// Se conserva mientras no se recargue la página (los nodos guardan sus botones y tareas en curso).
const historial = [];
let lista = null;

const SUGERENCIAS = [
  { texto: "¿Cuántos clientes hay por ciudad?", permiso: "contar" },
  { texto: "Resumen de los clientes interesados en seguro educativo", permiso: "resumen" },
  { texto: "Plantilla de mensaje para clientes de seguro de vida", permiso: "mensaje_segmento" },
  { texto: "Lista los clientes de seguro educativo en Medellín", permiso: "listar" },
  { texto: "Hazme un mensaje de WhatsApp para ", permiso: "mensaje_cliente", completar: true },
  { texto: "/borradores requiere_revision", permiso: "ver_mensajes" },
];

function agregar(nodo) {
  historial.push(nodo);
  if (lista) {
    lista.append(nodo);
    lista.scrollTop = lista.scrollHeight;
  }
  return nodo;
}

const filaYo = (texto) => h("div", { class: "chat-fila yo" }, h("div", { class: "burbuja" }, texto));

function filaBot(contenido, ancha = false) {
  const burbuja = h("div", { class: `burbuja ${ancha ? "ancha" : ""}` }, contenido);
  const fila = h("div", { class: "chat-fila bot" }, h("div", { class: "avatar-bot" }, icono("sparkle")), burbuja);
  return { fila, burbuja };
}

const pensando = (texto) => h("div", { class: "fila" }, h("span", { class: "escribiendo" }, h("span"), h("span"), h("span")), h("em", { class: "muted" }, texto));

function chipIntencion(i) {
  if (!i) return null;
  return h("div", { class: "intencion" }, icono("sparkle"), "Entendí:",
    h("span", { class: "badge badge-info" }, ACCIONES[i.accion] || i.accion),
    i.agrupar_por ? h("span", { class: "chip chip-estatico" }, `por ${etiqueta(i.agrupar_por).toLowerCase()}`) : null,
    Object.keys(i.filtros || {}).length ? chipsFiltros(i.filtros) : null,
    i.canal ? h("span", { class: "chip chip-estatico" }, canalTexto(i.canal)) : null,
    i.nombre ? h("span", { class: "chip chip-estatico" }, i.nombre) : null);
}

// ------------------------------------------------------------------ acciones que nacen de una respuesta
async function generarBorrador(clave, canal, nombre) {
  const { fila, burbuja } = filaBot(pensando(`Redactando borrador por ${canalTexto(canal)} para ${nombre || "el cliente"}… (validación automática incluida)`), true);
  agregar(fila);
  try {
    burbuja.replaceChildren(resultadoBorrador(await post("/api/clientes/borrador", { clave, canal })));
  } catch (e) {
    burbuja.replaceChildren(alerta(e.message, "peligro"));
  }
}

function elegirCanal(alElegir) {
  return h("div", { class: "fila" },
    h("button", { class: "btn btn-sm", onclick: (e) => { e.currentTarget.parentElement.querySelectorAll("button").forEach((b) => { b.disabled = true; }); alElegir("whatsapp"); } }, icono("whatsapp"), "WhatsApp"),
    h("button", { class: "btn btn-sm", onclick: (e) => { e.currentTarget.parentElement.querySelectorAll("button").forEach((b) => { b.disabled = true; }); alElegir("correo"); } }, icono("mail"), "Correo"));
}

function confirmarLote(r) {
  const caja = h("div", { class: "pila-sm" });
  let canal = r.canal || "whatsapp";
  const procesar = Math.min(r.total, r.limite);
  const lanzar = h("button", { class: "btn btn-primario btn-sm" }, icono("play"), "Generar borradores");
  const cancelar = h("button", { class: "btn btn-sm" }, "Cancelar");
  cancelar.addEventListener("click", () => caja.replaceChildren(h("span", { class: "muted" }, "Cancelado. No se generó nada.")));
  lanzar.addEventListener("click", async () => {
    const t = await conBoton(lanzar, () => post("/api/mensajes/lote", { filtros: r.filtros, canal }));
    if (t) caja.replaceChildren(tareaLote(t.tarea));
  });
  caja.append(
    h("div", {}, h("strong", {}, `Se generarán borradores para ${num(procesar)} cliente(s)`),
      r.total > r.limite ? h("span", { class: "muted" }, ` (el grupo tiene ${num(r.total)}; el tope por lote es ${r.limite})`) : null),
    h("div", { class: "fila" }, chipsFiltros(r.filtros)),
    h("div", { class: "fila" }, h("span", { class: "muted" }, "Canal:"),
      segmentado([{ valor: "whatsapp", texto: "WhatsApp", icono: "whatsapp" }, { valor: "correo", texto: "Correo", icono: "mail" }], canal, (v) => { canal = v; })),
    h("span", { class: "muted pequeño" }, "Cada borrador pasa por la validación automática. Nada se envía: quedan para tu revisión."),
    r.total ? h("div", { class: "fila" }, lanzar, cancelar) : alerta("No hay clientes en ese grupo.", "warn"));
  return caja;
}

// ------------------------------------------------------------------ representación de cada tipo de respuesta
function respuesta(r) {
  const cuerpo = [chipIntencion(r.intencion)];
  switch (r.tipo) {
    case "conteo":
      cuerpo.push(tarjetaConteo(r, { onValor: (f) => irA("segmentos", { ...r.intencion.filtros, [r.dimension]: f.valor }) }));
      break;
    case "listado":
      if (!r.filas.length) {
        cuerpo.push(alerta("Sin resultados.", "warn"), diagnostico(r.diagnostico));
      } else {
        cuerpo.push(
          h("div", { class: "fila", style: { marginBottom: "8px" } }, h("strong", {}, `${num(r.filas.length)} cliente(s)`),
            r.truncado ? h("span", { class: "muted" }, `· se muestran los primeros ${r.limite}; usa «contar» para el total`) : null),
          tablaClientes(r.filas, { onAbrir: (f) => abrirCliente(f.clave_cliente), agruparPor: r.agrupar_por }));
        if (puede("mensajes_lote") && Object.keys(r.filtros || {}).length) {
          const b = h("button", { class: "btn btn-sm", style: { marginTop: "8px" } }, icono("mail"), "Generar borradores para este grupo");
          b.addEventListener("click", async () => {
            const datos = await conBoton(b, () => Promise.all([catalogo(), post("/api/contar", { filtros: r.filtros, agrupar_por: "segmento" })]));
            if (!datos) return;
            b.disabled = true;
            const [cat, conteo] = datos;
            agregar(filaBot(confirmarLote({ filtros: r.filtros, canal: null, total: conteo.total, limite: cat.limite_lote }), true).fila);
          });
          cuerpo.push(b);
        }
      }
      break;
    case "resumen":
      cuerpo.push(tarjetaResumen(r.resumen));
      break;
    case "plantilla":
      cuerpo.push(tarjetaPlantilla(r));
      break;
    case "borrador":
      cuerpo.push(resultadoBorrador(r));
      break;
    case "mensaje":
      cuerpo.push(tarjetaMensaje(r.mensaje));
      break;
    case "elegir_cliente":
      cuerpo.push(h("p", {}, r.texto), h("div", { class: "pila-sm", style: { marginTop: "8px" } }, r.opciones.map((o) => {
        const b = h("button", { class: "btn btn-sm", style: { justifyContent: "flex-start" } }, icono("user"), o.nombre,
          h("span", { class: "muted" }, ` · ${o.ciudad || "sin ciudad"} · ${o.clave_cliente}`));
        b.addEventListener("click", () => {
          b.parentElement.querySelectorAll("button").forEach((x) => { x.disabled = true; });
          if (r.canal) { generarBorrador(o.clave_cliente, r.canal, o.nombre); return; }
          const { fila } = filaBot([h("p", {}, `¿Por qué canal le escribimos a ${o.nombre}?`), elegirCanal((c) => generarBorrador(o.clave_cliente, c, o.nombre))]);
          agregar(fila);
        });
        return b;
      })));
      break;
    case "elegir_canal":
      cuerpo.push(h("p", {}, `${r.texto} (${r.cliente.nombre})`), h("div", { style: { marginTop: "8px" } },
        elegirCanal((c) => generarBorrador(r.cliente.clave_cliente, c, r.cliente.nombre))));
      break;
    case "confirmar_lote":
      cuerpo.push(confirmarLote(r));
      break;
    case "aviso":
      cuerpo.push(alerta(r.texto, "warn"));
      break;
    default:
      cuerpo.push(h("div", { class: "texto-pre" }, r.texto || JSON.stringify(r, null, 2)));
  }
  return cuerpo;
}

const ANCHAS = new Set(["conteo", "listado", "resumen", "plantilla", "borrador", "mensaje", "confirmar_lote"]);

async function enviar(texto) {
  agregar(filaYo(texto));
  const { fila, burbuja } = filaBot(pensando(texto.startsWith("/") ? "Ejecutando comando…" : "Interpretando con el modelo local… puede tardar unos segundos."));
  agregar(fila);
  try {
    const r = await post("/api/asistente", { pregunta: texto });
    if (ANCHAS.has(r.tipo)) burbuja.classList.add("ancha");
    burbuja.replaceChildren(...respuesta(r).filter(Boolean));
  } catch (e) {
    burbuja.replaceChildren(alerta(e.message, "peligro"));
  }
  if (lista) lista.scrollTop = lista.scrollHeight;
}

// ------------------------------------------------------------------ vista
export function render(cont) {
  lista = h("div", { class: "chat-lista", "aria-live": "polite" });
  const entrada = h("textarea", { rows: 1, placeholder: "Escribe tu solicitud… (Enter envía, Shift+Enter cambia de línea)" });
  const boton = h("button", { class: "btn btn-primario", title: "Enviar" }, icono("send"));
  let ocupado = false;

  const ajustar = () => {
    entrada.style.height = "auto";
    entrada.style.height = `${Math.min(entrada.scrollHeight, 160)}px`;
    entrada.style.overflowY = entrada.scrollHeight > 160 ? "auto" : "hidden";
  };
  const mandar = async () => {
    const texto = entrada.value.trim();
    if (!texto || ocupado) return;
    entrada.value = "";
    ajustar();
    ocupado = true;
    boton.disabled = true;
    bienvenida.remove();
    await enviar(texto);
    ocupado = false;
    boton.disabled = false;
    entrada.focus();
  };
  entrada.addEventListener("input", ajustar);
  entrada.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); mandar(); } });
  boton.addEventListener("click", mandar);

  const sugerencias = SUGERENCIAS.filter((s) => puede(s.permiso)).map((s) => h("button", {
    class: "chip", onclick: () => { entrada.value = s.texto; ajustar(); entrada.focus(); if (!s.completar) mandar(); },
  }, s.texto.trim()));

  const bienvenida = h("div", { class: "vacio", style: { padding: "40px 16px" } },
    h("div", { class: "avatar-bot", style: { width: "44px", height: "44px" } }, icono("sparkle", "ico-lg")),
    h("strong", { style: { color: "var(--text)" } }, "¿Qué necesitas consultar?"),
    h("div", {}, "El modelo solo traduce tu pregunta a una intención; las cifras salen de la base y los permisos los aplica el sistema."),
    h("div", { class: "sugerencias", style: { justifyContent: "center", marginTop: "8px" } }, sugerencias));

  if (historial.length) lista.append(...historial);
  else lista.append(bienvenida);

  const limpiar = h("button", { class: "btn btn-fantasma btn-sm", title: "Vaciar la conversación" }, icono("trash"), "Limpiar");
  limpiar.addEventListener("click", () => { historial.length = 0; lista.replaceChildren(bienvenida); });

  const comandos = puede("ver_mensajes") ? h("div", { class: "card pila-sm" }, h("h3", {}, "Comandos directos"),
    h("p", { class: "muted pequeño" }, "No pasan por el modelo: un cambio de estado nunca depende de una interpretación."),
    h("div", { class: "ayuda-lista pequeño" },
      ["/borradores [estado]", "/ver ID", "/aprobar ID", "/descartar ID", "/enviado ID"].map((c) => h("div", {}, h("code", {}, c))))) : null;

  cont.append(h("div", { class: "chat" },
    h("div", { class: "card chat-panel" }, lista, h("div", { class: "chat-form" }, entrada, boton)),
    h("div", { class: "pila chat-ayuda" },
      h("div", { class: "card pila-sm" }, h("div", { class: "fila" }, h("h3", { style: { flex: "1" } }, "Ejemplos"), limpiar),
        h("div", { class: "sugerencias" }, SUGERENCIAS.filter((s) => puede(s.permiso)).map((s) => h("button", {
          class: "chip", onclick: () => { entrada.value = s.texto; ajustar(); entrada.focus(); },
        }, s.texto.trim())))),
      h("div", { class: "card pila-sm" }, h("h3", {}, "Qué puedo hacer"),
        h("ul", { class: "pequeño muted" },
          h("li", {}, "Contar y resumir grupos de clientes."),
          h("li", {}, "Redactar una plantilla de mensaje por segmento."),
          puede("listar") ? h("li", {}, "Listar clientes y abrir su ficha.") : null,
          puede("mensaje_cliente") ? h("li", {}, "Redactar borradores de WhatsApp o correo, uno a uno o en lote.") : null),
        h("p", { class: "muted pequeño" }, "Si pides un dato que no existe (hijos, salario…), no ejecuto la consulta para no ignorar tu criterio.")),
      comandos)));
  lista.scrollTop = lista.scrollHeight;
  entrada.focus();
  return () => { lista = null; };
}
