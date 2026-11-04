// Conocimiento de producto: revisión humana de lo extraído del sitio, ingesta con Firecrawl y prueba del RAG.
import { get, post } from "../api.js";
import { catalogo } from "../estado.js";
import { seguirTarea } from "../tarea.js";
import {
  alerta, badge, cabecera, campo, cargando, conBoton, confirmar, errorCaja, fecha, h, icono, num, pestañas,
  poner, segmentado, selector, tabla, toast, vacio,
} from "../ui.js";

let pestañaActiva = "pendiente";

function registroOperacion(r) {
  const lineas = (r.log || "").split("\n").filter(Boolean);
  toast(lineas[0] || "Listo.");
  return lineas.length > 1 ? alerta(h("div", { class: "texto-pre" }, r.log), "ok") : null;
}

export async function render(cont) {
  const cat = await catalogo();
  let resumen = [];
  const zonaResumen = h("div");
  const cuerpo = h("div", { class: "pila" });
  const tabs = pestañas([
    { id: "pendiente", texto: "Por revisar" }, { id: "activo", texto: "Aprobado" },
    { id: "ingesta", texto: "Ingesta web" }, { id: "rag", texto: "Probar búsqueda" },
  ], pestañaActiva, (id) => { pestañaActiva = id; mostrar(); });

  async function cargarResumen() {
    try {
      resumen = await get("/api/conocimiento/resumen");
    } catch (e) {
      zonaResumen.replaceChildren(errorCaja(e, cargarResumen));
      return;
    }
    const pend = resumen.reduce((a, r) => a + r.pendientes, 0);
    const act = resumen.reduce((a, r) => a + r.activos, 0);
    tabs.actualizar([
      { id: "pendiente", texto: "Por revisar", n: pend }, { id: "activo", texto: "Aprobado", n: act },
      { id: "ingesta", texto: "Ingesta web" }, { id: "rag", texto: "Probar búsqueda" },
    ]);
    zonaResumen.replaceChildren(h("details", { class: "card" },
      h("summary", {}, `Resumen por producto y categoría · ${num(pend)} por revisar · ${num(act)} aprobados`),
      h("div", { style: { marginTop: "12px" } }, tabla([
        { titulo: "Producto", valor: (r) => r.producto || "—" },
        { titulo: "Categoría", valor: (r) => r.categoria || "—" },
        { titulo: "Por revisar", valor: (r) => (r.pendientes ? badge(num(r.pendientes), "warn") : "0"), clase: "num" },
        { titulo: "Aprobados", valor: (r) => num(r.activos), clase: "num" },
        { titulo: "Manuales", valor: (r) => num(r.manuales), clase: "num" },
      ], resumen, { vacioTexto: "Aún no hay conocimiento cargado." }))));
  }

  function mostrar() {
    if (pestañaActiva === "ingesta") cuerpo.replaceChildren(vistaIngesta(cat, cargarResumen));
    else if (pestañaActiva === "rag") cuerpo.replaceChildren(vistaRag(resumen));
    else cuerpo.replaceChildren(vistaFragmentos(pestañaActiva, resumen, cargarResumen));
  }

  cont.append(
    cabecera("Conocimiento de producto", "Lo extraído del sitio queda pendiente hasta que lo apruebes. Solo lo aprobado llega al asistente (y se vectoriza al aprobar)."),
    zonaResumen, h("div", { class: "card pila" }, tabs.el, cuerpo));
  await cargarResumen();
  mostrar();
}

// ------------------------------------------------------------------ revisión / aprobado
function vistaFragmentos(estadoF, resumen, alCambiar) {
  const productos = [...new Set(resumen.map((r) => r.producto).filter(Boolean))].sort();
  const categorias = [...new Set(resumen.map((r) => r.categoria).filter(Boolean))].sort();
  const fProd = selector([{ valor: "", texto: "Todos los productos" }, ...productos], "");
  const fCat = selector([{ valor: "", texto: "Todas las categorías" }, ...categorias], "");
  const fQ = h("input", { type: "search", placeholder: "Buscar en título o contenido…" });
  const seleccion = new Set();
  const zona = h("div", { class: "pila" });
  const zonaLog = h("div");
  const contador = h("span", { class: "muted" });
  let total = 0;

  const pendiente = estadoF === "pendiente";
  const bLote = h("button", { class: `btn btn-sm ${pendiente ? "btn-primario" : "btn-peligro-suave"}`, disabled: true },
    icono(pendiente ? "check" : "x"), pendiente ? "Aprobar seleccionados" : "Desactivar seleccionados");
  const bTodos = pendiente ? h("button", { class: "btn btn-sm" }, icono("check"), "Aprobar todos los filtrados") : null;

  const actualizarSel = () => {
    contador.textContent = seleccion.size ? `${seleccion.size} seleccionado(s)` : `${num(total)} fragmento(s)`;
    bLote.disabled = !seleccion.size;
  };

  async function operar(boton, ruta, datos) {
    const r = await conBoton(boton, () => post(ruta, datos));
    if (!r) return;
    zonaLog.replaceChildren(registroOperacion(r) || "");
    seleccion.clear();
    await Promise.all([cargar(), alCambiar()]);
  }

  bLote.addEventListener("click", () => operar(bLote, `/api/conocimiento/${pendiente ? "aprobar" : "desactivar"}`, { ids: [...seleccion] }));
  if (bTodos) {
    bTodos.addEventListener("click", async () => {
      if (fQ.value.trim()) { toast("«Aprobar todos» filtra solo por producto y categoría: quita el texto de búsqueda o selecciona los fragmentos.", "info", 7000); return; }
      const alcance = [fProd.value && `producto «${fProd.value}»`, fCat.value && `categoría «${fCat.value}»`].filter(Boolean).join(" y ");
      const ok = await confirmar("¿Aprobar todos?", `Se aprobarán ${num(total)} fragmento(s) pendientes${alcance ? ` de ${alcance}` : ""}. El asistente los usará de inmediato.`, { boton: "Aprobar" });
      if (ok) operar(bTodos, "/api/conocimiento/aprobar", { todos: true, producto: fProd.value || null, categoria: fCat.value || null });
    });
  }

  function item(f) {
    const manual = !f.fuente_url;
    const check = h("input", { type: "checkbox", disabled: !pendiente && manual, title: manual ? "El conocimiento manual no se gestiona desde aquí" : "" });
    const fila = h("div", { class: "item" });
    check.addEventListener("change", () => {
      if (check.checked) seleccion.add(f.id_conocimiento); else seleccion.delete(f.id_conocimiento);
      fila.classList.toggle("sel", check.checked);
      actualizarSel();
    });
    const texto = h("div", { class: "item-texto recortado" }, f.contenido);
    const verMas = h("button", { class: "btn btn-fantasma btn-sm", onclick: () => { const r = texto.classList.toggle("recortado"); verMas.textContent = r ? "Ver todo" : "Ver menos"; } }, "Ver todo");
    const accion = pendiente
      ? h("button", { class: "btn btn-sm btn-ok" }, icono("check"), "Aprobar")
      : (manual ? null : h("button", { class: "btn btn-sm btn-peligro-suave" }, icono("x"), "Desactivar"));
    if (accion) accion.addEventListener("click", () => operar(accion, `/api/conocimiento/${pendiente ? "aprobar" : "desactivar"}`, { ids: [f.id_conocimiento] }));
    fila.append(h("div", {}, check), h("div", { class: "pila-sm" },
      h("div", { class: "item-cab" }, h("strong", {}, f.titulo), badge(f.producto, "info"), badge(f.categoria), manual ? badge("manual") : null,
        h("span", { class: "muted pequeño" }, `#${f.id_conocimiento} · ${fecha(f.fecha_actualizacion)}`)),
      texto,
      h("div", { class: "fila" }, f.contenido && f.contenido.length > 280 ? verMas : null,
        f.fuente_url ? h("a", { href: f.fuente_url, target: "_blank", rel: "noopener noreferrer", class: "pequeño fila", style: { gap: "4px" } }, icono("external"), "Fuente") : null,
        h("span", { class: "espaciador" }), accion)));
    return fila;
  }

  async function cargar() {
    zona.replaceChildren(cargando());
    seleccion.clear();
    const params = new URLSearchParams({ estado: estadoF, producto: fProd.value, categoria: fCat.value, q: fQ.value.trim() });
    try {
      const r = await get(`/api/conocimiento?${params}`);
      total = r.total;
      zona.replaceChildren(r.filas.length
        ? h("div", { class: "items" }, r.filas.map(item), r.total > r.filas.length ? h("span", { class: "muted pequeño" }, `Se muestran ${r.filas.length} de ${num(r.total)}. Filtra para ver el resto.`) : null)
        : vacio(pendiente ? "No hay fragmentos por revisar con esos filtros." : "No hay fragmentos aprobados con esos filtros.", pendiente ? "check" : "book"));
    } catch (e) {
      zona.replaceChildren(errorCaja(e, cargar));
    }
    actualizarSel();
  }

  fProd.addEventListener("change", cargar);
  fCat.addEventListener("change", cargar);
  fQ.addEventListener("keydown", (e) => { if (e.key === "Enter") cargar(); });
  cargar();

  return h("div", { class: "pila" },
    h("div", { class: "filtros-grid" }, campo("Producto", fProd), campo("Categoría", fCat), campo("Texto", fQ)),
    h("div", { class: "barra-acciones" }, contador, h("span", { class: "espaciador" }), bTodos, bLote),
    zonaLog, zona);
}

// ------------------------------------------------------------------ ingesta web
function vistaIngesta(cat, alTerminar) {
  let modo = "sitio";
  const zonaTareas = h("div", { class: "pila" });
  const checks = Object.entries(cat.productos_sitio).map(([clave, nombre]) => ({ clave, el: h("input", { type: "checkbox" }), nombre }));
  const sinPortafolio = h("input", { type: "checkbox" });
  const producto = h("input", { type: "text", value: "auto", list: "dl-productos-sitio" });
  const urls = h("textarea", { rows: 4, placeholder: "https://www.globalseguroscolombia.com/...\n(una URL por línea; deben ser del dominio configurado)" });
  const pdf = h("input", { type: "checkbox" });
  const pdfSolo = h("input", { type: "text", placeholder: "p. ej. clausulado" });
  const maxPdfs = h("input", { type: "number", value: "5", min: "1", max: "50" });
  const maxFrag = h("input", { type: "number", value: "120", min: "10", max: "500" });
  const tarifas = h("input", { type: "checkbox" });

  const bloqueSitio = h("div", { class: "pila-sm" },
    h("span", { class: "muted pequeño" }, "Productos (sin marcar ninguno = todo el catálogo):"),
    h("div", { class: "filtros-grid" }, checks.map((c) => h("label", { class: "check" }, c.el, c.nombre))),
    h("label", { class: "check" }, sinPortafolio, "Omitir la página de portafolio (/productos/)"));
  const bloqueScrape = h("div", { class: "pila-sm oculto" },
    campo("Producto", producto, "Nombre del producto tal como lo usa la base de clientes, o «auto» para deducirlo del título de cada sección."),
    h("datalist", { id: "dl-productos-sitio" }, h("option", { value: "auto" }), Object.values(cat.productos_sitio).map((n) => h("option", { value: n }))),
    campo("URLs", urls));

  const bIniciar = h("button", { class: "btn btn-primario" }, icono("play"), "Iniciar ingesta");
  bIniciar.addEventListener("click", async () => {
    const datos = {
      modo, pdf: pdf.checked, pdf_solo: pdfSolo.value.trim(), max_pdfs: Number(maxPdfs.value) || 5,
      max_fragmentos: Number(maxFrag.value) || 120, con_tarifas: tarifas.checked,
    };
    if (modo === "sitio") {
      datos.solo = checks.filter((c) => c.el.checked).map((c) => c.clave);
      datos.sin_portafolio = sinPortafolio.checked;
    } else {
      datos.producto = producto.value.trim() || "auto";
      datos.urls = urls.value.split(/\s+/).filter(Boolean);
      if (!datos.urls.length) { toast("Escribe al menos una URL.", "error"); return; }
    }
    const r = await conBoton(bIniciar, () => post("/api/conocimiento/ingesta", datos));
    if (r) zonaTareas.prepend(seguirTarea(r.tarea, { alTerminar: (_res, zona) => { zona.append(alerta("Terminado. Revisa lo extraído en «Por revisar».", "ok")); alTerminar(); } }));
  });

  const bVector = h("button", { class: "btn" }, icono("database"), "Actualizar índice vectorial");
  bVector.addEventListener("click", async () => {
    const r = await conBoton(bVector, () => post("/api/conocimiento/vectorizar"));
    if (r) toast(`Índice vectorial actualizado: ${num(r.vectorizados)} fragmento(s) vectorizados.`);
  });

  get("/api/tareas").then((ts) => ts.filter((t) => t.tipo === "ingesta_web" && t.estado === "en_curso")
    .forEach((t) => zonaTareas.append(seguirTarea(t, { alTerminar }))))
    .catch(() => {});

  return h("div", { class: "pila" },
    alerta([h("strong", {}, "Firecrawl cobra por página. "),
      "Una página del sitio ≈ 1 crédito; cada página de un PDF cuesta 1 crédito adicional. Lo extraído queda pendiente: no llega al asistente hasta que lo apruebes."], "info"),
    h("div", { class: "fila" }, segmentado([{ valor: "sitio", texto: "Catálogo del sitio", icono: "globe" }, { valor: "scrape", texto: "Páginas sueltas", icono: "link" }], modo, (v) => {
      modo = v;
      bloqueSitio.classList.toggle("oculto", v !== "sitio");
      bloqueScrape.classList.toggle("oculto", v !== "scrape");
    })),
    bloqueSitio, bloqueScrape,
    h("details", {}, h("summary", {}, "Clausulados en PDF (opcional, cuesta más créditos)"),
      h("div", { class: "pila-sm", style: { marginTop: "10px" } },
        h("label", { class: "check" }, pdf, "Descargar también los PDFs enlazados"),
        h("div", { class: "filtros-grid" }, campo("Solo PDFs que contengan", pdfSolo), campo("Máximo de PDFs", maxPdfs), campo("Máx. fragmentos por PDF", maxFrag)),
        h("label", { class: "check" }, tarifas, "Incluir PDFs de tarifas (por defecto se omiten)"),
        h("span", { class: "muted pequeño" }, "Sin marcar «Descargar», solo se listan los PDFs encontrados en el registro."))),
    h("div", { class: "fila" }, bVector, h("span", { class: "espaciador" }), bIniciar),
    zonaTareas);
}

// ------------------------------------------------------------------ prueba de recuperación
function vistaRag(resumen) {
  const productos = [...new Set(resumen.map((r) => r.producto).filter(Boolean))].sort();
  const producto = selector([{ valor: "", texto: "Todos los productos" }, ...productos], "");
  const consulta = h("textarea", { rows: 2, placeholder: "p. ej. ¿qué cubre si el tomador fallece?" });
  const k = h("input", { type: "number", value: "5", min: "1", max: "20" });
  const zona = h("div", { class: "pila" });
  const bBuscar = h("button", { class: "btn btn-primario" }, icono("search"), "Probar");
  bBuscar.addEventListener("click", async () => {
    if (consulta.value.trim().length < 2) { toast("Escribe una consulta.", "error"); return; }
    const r = await conBoton(bBuscar, () => post("/api/conocimiento/buscar", { producto: producto.value, consulta: consulta.value.trim(), k: Number(k.value) || 5 }));
    if (!r) return;
    poner(zona,
      h("div", { class: "fila" }, h("span", { class: "muted" }, "Modo:"), badge(r.modo === "vectorial" ? "Vectorial (solo lo relevante)" : "Completo (todo el producto)", r.modo === "vectorial" ? "ok" : "warn"),
        h("span", { class: "muted" }, `· ${r.titulos.length} fragmento(s) al modelo`)),
      r.aviso ? alerta(r.aviso, "warn") : null,
      r.fragmentos.length
        ? h("div", { class: "items" }, r.fragmentos.map((f) => h("div", { class: "item", style: { gridTemplateColumns: "1fr" } }, h("div", { class: "pila-sm" },
          h("div", { class: "item-cab" }, h("strong", {}, f.titulo), badge(f.categoria),
            f.similitud != null ? badge(`similitud ${f.similitud.toFixed(2)}`, f.similitud > 0.6 ? "ok" : "info") : badge("regla de negocio · siempre incluida", "primario")),
          h("div", { class: "item-texto" }, f.contenido)))))
        : h("div", { class: "pila-sm" }, h("span", { class: "muted" }, "Texto que recibiría el modelo:"), h("div", { class: "mensaje-cuerpo texto-pre" }, r.texto)));
  });
  return h("div", { class: "pila" },
    h("p", { class: "muted" }, "Comprueba qué fragmentos recibiría el modelo para una pregunta. Las reglas de negocio del producto siempre se incluyen."),
    h("div", { class: "filtros-grid" }, campo("Producto", producto), campo("Fragmentos (k)", k)),
    campo("Consulta", consulta),
    h("div", { class: "fila" }, h("span", { class: "espaciador" }), bBuscar),
    zona);
}
