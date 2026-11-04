// Piezas de negocio reutilizadas por varias vistas: conteos, resúmenes, clientes, borradores y lotes.
import { get, post } from "./api.js";
import { catalogo, opciones, puede } from "./estado.js";
import { TODAS, constructorFiltros } from "./filtros.js";
import { seguirTarea } from "./tarea.js";
import {
  ESTADOS, alerta, badge, badgeEstado, barras, cajon, canalTexto, cargando, chipsFiltros, confirmar,
  conBoton, copiar, errorCaja, etiqueta, fecha, h, icono, legible, modal, num, poner, segmentado, tabla, toast, vacio,
} from "./ui.js";

export function kpi(etq, valor, { sub, ico, href, destacado } = {}) {
  return h(href ? "a" : "div", { class: `card kpi ${destacado ? "destacado" : ""}`, href },
    h("span", { class: "etq" }, ico ? icono(ico) : null, etq),
    h("span", { class: "valor" }, valor),
    sub ? h("span", { class: "sub" }, sub) : null);
}

export function dato(etq, valor) {
  return h("div", { class: "dato" }, h("span", {}, etq), h("strong", {}, valor == null || valor === "" ? "—" : String(valor)));
}

// ------------------------------------------------------------------ agregados
export function tarjetaConteo(res, { onValor } = {}) {
  return h("div", { class: "pila-sm" },
    h("div", { class: "fila" }, h("h3", {}, `Clientes por ${etiqueta(res.dimension).toLowerCase()}`),
      h("span", { class: "muted" }, `· total ${num(res.total)}`)),
    res.filas.length ? barras(res.filas, { onClick: onValor, max: 15, total: res.total }) : vacio("Sin resultados."),
    res.ocultos ? alerta(`${res.ocultos} grupo(s) con menos de ${res.k_min} personas se ocultan por privacidad (k-anonimato).`, "info") : null);
}

export function tarjetaResumen(r) {
  const top = (titulo, lista) => h("div", { class: "pila-sm" }, h("h3", {}, titulo),
    lista && lista.length ? barras(lista.map(([valor, n]) => ({ valor, n })), { total: r.total }) : h("span", { class: "muted" }, "Sin datos"));
  return h("div", { class: "pila" },
    h("div", { class: "kpis" },
      kpi("Clientes en el grupo", num(r.total), { ico: "users" }),
      kpi("Edad promedio", r.edad_promedio != null ? `${num(r.edad_promedio)} años` : "—", { ico: "user" })),
    h("div", { class: "grid-3" },
      top("Ciudades principales", r.top_ciudad),
      top("Profesiones principales", r.top_profesion),
      top("Productos de interés", r.top_producto_interes)));
}

export function diagnostico(filas) {
  if (!filas || !filas.length) return null;
  return h("div", { class: "pila-sm" }, h("span", { class: "muted pequeño" }, "Diagnóstico por filtro (cuántos cumple cada uno por separado):"),
    tabla([{ titulo: "Filtro", valor: (f) => f.filtro }, { titulo: "Clientes", valor: (f) => num(f.n), clase: "num" }], filas));
}

export function tarjetaPlantilla({ texto, errores, total }) {
  return h("div", { class: "pila-sm" },
    h("div", { class: "fila" }, h("h3", {}, "Plantilla de mensaje"), h("span", { class: "muted" }, `· para ${num(total)} clientes`),
      h("span", { class: "espaciador" }),
      h("button", { class: "btn btn-sm btn-fantasma", onclick: () => copiar(texto) }, icono("copy"), "Copiar")),
    h("div", { class: "mensaje-cuerpo" }, texto),
    h("span", { class: "muted pequeño" }, "{nombre} se reemplaza por el nombre de cada cliente."),
    errores && errores.length ? alerta([h("strong", {}, "No pasó la validación tras 3 intentos:"), h("ul", {}, errores.map((e) => h("li", {}, e)))], "warn") : null);
}

// ------------------------------------------------------------------ clientes
function contacto(f) {
  const correo = f.tiene_correo ?? Boolean(f.correo);
  const celular = f.tiene_celular ?? Boolean(f.celular);
  return h("span", { class: "fila", style: { gap: "4px" } },
    h("span", { title: correo ? (f.correo || "Correo válido") : "Sin correo", style: { color: correo ? "var(--ok)" : "var(--border-strong)" } }, icono("mail")),
    h("span", { title: celular ? (f.celular || "Celular válido") : "Sin celular", style: { color: celular ? "var(--ok)" : "var(--border-strong)" } }, icono("whatsapp")));
}

export function tablaClientes(filas, { onAbrir, agruparPor } = {}) {
  const cols = [
    { titulo: "Cliente", valor: (f) => [h("strong", {}, f.nombre || "—"), h("span", { class: "celda-sub mono" }, f.clave_cliente)] },
    { titulo: "Edad", valor: (f) => f.edad ?? "—", clase: "num" },
    { titulo: "Ciudad", valor: (f) => f.ciudad || "—" },
    { titulo: "Profesión", valor: (f) => f.profesion || "—" },
    { titulo: "Producto de interés", valor: (f) => f.producto_interes || "—" },
    { titulo: "Segmento", valor: (f) => (f.segmento ? badge(f.segmento) : "—") },
    { titulo: "Contacto", valor: contacto },
  ];
  const opcionesTabla = { onFila: onAbrir ? (f) => onAbrir(f) : null };
  if (!agruparPor) return tabla(cols, filas, opcionesTabla);
  const grupos = {};
  for (const f of filas) (grupos[legible(f[agruparPor])] ||= []).push(f);
  return h("div", { class: "pila" }, Object.entries(grupos).sort().map(([g, fs]) => h("div", { class: "pila-sm" },
    h("h3", {}, `${g} `, h("span", { class: "muted" }, `(${fs.length})`)), tabla(cols, fs, opcionesTabla))));
}

export function abrirCliente(clave) {
  const c = cajon("Cliente");
  const cargar = async () => {
    c.cuerpo.replaceChildren(cargando());
    try {
      pintar(await post("/api/clientes/ficha", { clave }));
    } catch (e) {
      c.cuerpo.replaceChildren(errorCaja(e, cargar));
    }
  };

  function pintar(d) {
    const f = d.ficha;
    c.setTitulo(f.nombre || "Cliente");
    const zonaGen = h("div", { class: "pila" });
    const zonaPerfil = h("div");
    const botones = h("div", { class: "fila" });

    if (puede("mensaje_cliente")) {
      const motivo = (canal) => {
        if (!f.consentimiento) return "Sin consentimiento registrado";
        if (!f.producto_interes) return "Sin producto de interés";
        if (canal === "whatsapp" && !f.tiene_celular) return "Sin celular válido";
        if (canal === "correo" && !f.tiene_correo) return "Sin correo válido";
        return null;
      };
      for (const canal of ["whatsapp", "correo"]) {
        const bloqueo = motivo(canal);
        const b = h("button", { class: `btn ${canal === "whatsapp" ? "btn-primario" : ""}`, disabled: Boolean(bloqueo), title: bloqueo || `Genera un borrador por ${canalTexto(canal)}` },
          icono(canal === "whatsapp" ? "whatsapp" : "mail"), `Borrador ${canalTexto(canal)}`);
        b.addEventListener("click", async () => {
          const r = await conBoton(b, () => post("/api/clientes/borrador", { clave, canal }));
          if (r) zonaGen.prepend(resultadoBorrador(r, { onCambio: cargarMensajes }));
        });
        botones.append(b);
      }
      const bPerfil = h("button", { class: "btn", title: "Perfil consolidado con el modelo local, solo con datos explícitos" }, icono("sparkle"), d.perfil ? "Regenerar perfil IA" : "Generar perfil IA");
      bPerfil.addEventListener("click", async () => {
        const r = await conBoton(bPerfil, () => post("/api/clientes/perfil", { clave }));
        if (r) { pintarPerfil(r.perfil); toast("Perfil generado y guardado."); }
      });
      botones.append(bPerfil);
    }

    const pintarPerfil = (p) => zonaPerfil.replaceChildren(p
      ? h("div", { class: "pila-sm" }, dato("Segmento", p.segmento), dato("Características relevantes", p.caracteristicas_relevantes), dato("Perfil consolidado", p.perfil_consolidado))
      : h("span", { class: "muted" }, "Aún no tiene perfil generado."));
    pintarPerfil(d.perfil);

    const zonaMensajes = h("div");
    const pintarMensajes = (msgs) => zonaMensajes.replaceChildren(tabla([
      { titulo: "#", valor: (m) => m.id_mensaje, clase: "num" },
      { titulo: "Canal", valor: (m) => canalTexto(m.canal) },
      { titulo: "Producto", valor: (m) => m.producto || "—" },
      { titulo: "Estado", valor: (m) => badgeEstado(m.estado) },
      { titulo: "Fecha", valor: (m) => fecha(m.fecha_creacion) },
    ], msgs, { onFila: (m) => abrirMensaje(m.id_mensaje, { onCambio: cargarMensajes }), vacioTexto: "Aún no tiene borradores." }));
    async function cargarMensajes() {
      try { pintarMensajes((await post("/api/clientes/ficha", { clave })).mensajes); } catch { /* se queda la lista anterior */ }
    }
    pintarMensajes(d.mensajes);

    const estadoHecho = (x) => (x.activo ? badge("Aprobado", "ok") : x.descartado ? badge("Descartado") : badge("Pendiente", "warn"));

    const registros = d.registros || [];
    const comoSeUnio = (r) => ({
      automatico: badge(`unido automáticamente${r.puntaje != null ? ` (${num(r.puntaje)})` : ""}`, "ok"),
      manual: badge(`unido por ${r.decidido_por || "un administrador"}`, "info"),
      separado: badge("separado"),
    }[r.metodo] || badge("registro base"));
    const separarBoton = (r) => {
      const b = h("button", { class: "btn btn-sm btn-peligro-suave", title: "Sacar este registro: no es la misma persona" }, icono("split"), "Separar");
      b.addEventListener("click", async () => {
        if (!(await confirmar("¿Separar este registro?", `El registro #${r.id_registro} (${r.nombre}) quedará como un cliente aparte y no se volverá a unir con este automáticamente. Los borradores y el perfil IA se quedan en ${f.clave_cliente}.`, { boton: "Separar", peligro: true }))) return;
        const res = await conBoton(b, () => post("/api/clientes/separar", { id_registro: r.id_registro }));
        if (res) { toast(`Registro #${r.id_registro} separado como ${res.clave_cliente}.`); cargar(); }
      });
      return b;
    };
    const seccionRegistros = registros.length > 1 ? h("div", { class: "card pila-sm" },
      h("h2", {}, `Registros de origen (${registros.length})`),
      h("p", { class: "muted pequeño" }, "Este perfil une varios registros de la tabla clientes. De cada campo se toma el dato más reciente; el nombre, en su versión mejor escrita."),
      tabla([
        { titulo: "#", valor: (r) => r.id_registro, clase: "num" },
        { titulo: "Registro", valor: (r) => [r.nombre || "—", h("span", { class: "celda-sub" }, r.correo || "sin correo"), h("span", { class: "celda-sub" }, r.celular || "sin celular")] },
        { titulo: "Datos", valor: (r) => [`${r.edad ?? "—"} años · ${r.ciudad || "—"}`, h("span", { class: "celda-sub" }, r.profesion || "—")] },
        { titulo: "Origen", valor: (r) => [r.medio || "—", h("span", { class: "celda-sub" }, fecha(r.fecha_registro).split(",")[0])] },
        { titulo: "", valor: (r) => h("div", { class: "pila-sm" }, comoSeUnio(r), puede("admin_clientes") ? separarBoton(r) : null) },
      ], registros)) : null;
    const varios = (lista) => (lista && lista.length > 1 ? lista.join(" · ") : null);

    poner(c.cuerpo,
      h("div", { class: "card pila" },
        h("div", { class: "fila" },
          f.segmento ? badge(f.segmento, "info") : null,
          f.rango_edad ? badge(f.rango_edad) : null,
          f.consentimiento ? badge("Con consentimiento", "ok") : badge("Sin consentimiento", "peligro"),
          h("span", { class: "muted mono pequeño" }, f.clave_cliente)),
        h("div", { class: "datos-grid" },
          dato("Género", f.genero), dato("Edad", f.edad), dato("Ciudad", f.ciudad), dato("Profesión", f.profesion),
          dato("Universidad", f.universidad), dato("Producto de interés", f.producto_interes),
          dato("Correo", f.tiene_correo ? f.correo : "Sin correo válido"), dato("Celular", f.tiene_celular ? f.celular : "Sin celular válido"),
          varios(f.correos) ? dato("Todos sus correos", varios(f.correos)) : null,
          varios(f.celulares) ? dato("Todos sus celulares", varios(f.celulares)) : null,
          varios(f.productos_interes) ? dato("Productos de interés", varios(f.productos_interes)) : null),
        botones.childNodes.length ? botones : null),
      zonaGen,
      seccionRegistros,
      h("div", { class: "card pila-sm" }, h("h2", {}, "Perfil IA"), zonaPerfil),
      h("div", { class: "card pila-sm" }, h("h2", {}, "Borradores del cliente"), zonaMensajes),
      h("div", { class: "card pila-sm" }, h("h2", {}, "Hechos de perfil público"),
        d.hechos.length
          ? h("div", { class: "items" }, d.hechos.map((x) => h("div", { class: "item", style: { gridTemplateColumns: "1fr" } },
            h("div", {}, h("div", { class: "item-cab" }, badge(x.categoria, "info"), h("span", { class: "muted pequeño" }, x.red), h("span", { class: "espaciador" }), estadoHecho(x)),
              h("div", { class: "item-texto" }, x.contenido)))))
          : h("span", { class: "muted" }, "Sin hechos de perfiles públicos vinculados a este cliente."),
        h("span", { class: "muted pequeño" }, "Solo los hechos aprobados se usan al redactar borradores.")));
  }
  cargar();
}

// ------------------------------------------------------------------ borradores
const ACCION_ESTADO = {
  aprobado: { texto: "Aprobar", clase: "btn-primario", ico: "check" },
  enviado: { texto: "Marcar enviado", clase: "", ico: "send" },
  descartado: { texto: "Descartar", clase: "btn-peligro-suave", ico: "x", confirmar: true },
};

export function tarjetaMensaje(m, { onCambio } = {}) {
  const el = h("article", { class: "mensaje card" });
  const pintar = (m) => {
    const errores = Array.isArray(m.errores_validacion) ? m.errores_validacion : m.errores_validacion ? [String(m.errores_validacion)] : [];
    const textoCompleto = m.asunto ? `${m.asunto}\n\n${m.cuerpo}` : m.cuerpo;
    poner(el,
      h("header", { class: "mensaje-cab" },
        h("div", {},
          h("div", { class: "mensaje-titulo" }, icono(m.canal === "whatsapp" ? "whatsapp" : "mail"), h("strong", {}, m.nombre || m.clave_cliente), h("span", { class: "muted" }, `#${m.id_mensaje}`)),
          h("div", { class: "muted pequeño" }, [canalTexto(m.canal), m.producto || "sin producto", m.creado_por ? `creado por ${m.creado_por}` : null].filter(Boolean).join(" · "))),
        badgeEstado(m.estado)),
      m.asunto ? h("div", { class: "mensaje-asunto" }, h("span", { class: "muted" }, "Asunto: "), m.asunto) : null,
      h("div", { class: `mensaje-cuerpo ${m.canal}` }, m.cuerpo),
      errores.length ? alerta([h("strong", {}, "No pasó la validación automática"), h("ul", {}, errores.map((e) => h("li", {}, e)))], "warn") : null,
      h("footer", { class: "mensaje-acciones" },
        h("button", { class: "btn btn-sm btn-fantasma", onclick: () => copiar(textoCompleto) }, icono("copy"), "Copiar"),
        m.clave_cliente && puede("listar") ? h("button", { class: "btn btn-sm btn-fantasma", onclick: () => abrirCliente(m.clave_cliente) }, icono("user"), "Ver cliente") : null,
        h("span", { class: "espaciador" }),
        puede("cambiar_estado") ? (m.transiciones || []).map((t) => botonEstado(m, t)) : null));
  };
  const botonEstado = (m, nuevo) => {
    const a = ACCION_ESTADO[nuevo] || { texto: nuevo, clase: "", ico: "check" };
    const b = h("button", { class: `btn btn-sm ${a.clase}` }, icono(a.ico), a.texto);
    b.addEventListener("click", async () => {
      if (a.confirmar && !(await confirmar("¿Descartar este borrador?",
        "Un borrador descartado no se puede recuperar. Para este cliente, producto y canal podrás generar uno nuevo.", { boton: "Descartar", peligro: true }))) return;
      const r = await conBoton(b, () => post(`/api/mensajes/${m.id_mensaje}/estado`, { estado: nuevo }));
      if (r) { toast(r.texto); pintar(r.mensaje); if (onCambio) onCambio(r.mensaje); }
    });
    return b;
  };
  pintar(m);
  return el;
}

export function resultadoBorrador(r, { onCambio } = {}) {
  const p = r.resultado;
  if (p.estado_proceso === "omitido") return alerta(`No se generó el borrador para ${r.cliente.nombre}: ${p.motivo}.`, "warn");
  return h("div", { class: "pila-sm" },
    p.estado_proceso === "existente"
      ? alerta(`Ya existe el borrador #${p.id} (${(ESTADOS[p.estado] || {}).texto || p.estado}) para este cliente, producto y canal. Si quieres uno nuevo, descártalo primero.`, "info")
      : p.estado === "requiere_revision" ? alerta("El borrador no pasó todas las validaciones tras 3 intentos: revísalo antes de usarlo.", "warn") : null,
    r.mensaje ? tarjetaMensaje(r.mensaje, { onCambio }) : null);
}

export function abrirMensaje(id, { onCambio } = {}) {
  const cuerpo = h("div", {}, cargando());
  modal({ titulo: `Borrador #${id}`, contenido: cuerpo });
  get(`/api/mensajes/${id}`)
    .then((m) => cuerpo.replaceChildren(tarjetaMensaje(m, { onCambio })))
    .catch((e) => cuerpo.replaceChildren(errorCaja(e)));
}

// ------------------------------------------------------------------ lotes
export async function abrirLote(iniciales = {}, { alLanzar } = {}) {
  let ops, cat;
  try { [ops, cat] = await Promise.all([opciones(), catalogo()]); } catch (e) { toast(e.message, "error"); return; }
  let canal = "whatsapp";
  const filtros = constructorFiltros({ opciones: ops, iniciales, dims: TODAS.filter((d) => d !== "tiene_correo" && d !== "tiene_celular") });
  const previa = h("div", { class: "muted" }, "Define el grupo y pulsa «Contar» para ver cuántos clientes incluye.");
  const bContar = h("button", { class: "btn btn-sm" }, icono("users"), "Contar");
  bContar.addEventListener("click", async () => {
    const r = await conBoton(bContar, () => post("/api/contar", { filtros: filtros.valores(), agrupar_por: "segmento" }));
    if (r) previa.textContent = `${num(r.total)} clientes en el grupo. Se procesan hasta ${cat.limite_lote} (los primeros por nombre); los que no tengan ${canal === "whatsapp" ? "celular" : "correo"} válido o consentimiento se omiten.`;
  });
  modal({
    titulo: "Generar borradores en lote",
    contenido: [
      alerta("El modelo redacta un borrador por cliente y cada uno pasa por la validación automática. Nada se envía: quedan para tu revisión en Borradores.", "info"),
      h("div", { class: "campo" }, h("span", {}, "Canal"),
        segmentado([{ valor: "whatsapp", texto: "WhatsApp", icono: "whatsapp" }, { valor: "correo", texto: "Correo", icono: "mail" }], canal, (v) => { canal = v; })),
      h("h3", {}, "Grupo de clientes"), filtros.el,
      h("div", { class: "fila" }, bContar, previa),
    ],
    acciones: [
      { texto: "Cancelar" },
      {
        texto: "Generar borradores", primario: true, icono: "play",
        accion: async (cerrar, boton) => {
          const f = filtros.valores();
          if (!Object.keys(f).length) { toast("Indica al menos un filtro para definir el grupo.", "error"); return; }
          const r = await conBoton(boton, () => post("/api/mensajes/lote", { filtros: f, canal }));
          if (r) { cerrar(); if (alLanzar) alLanzar(r.tarea); }
        },
      },
    ],
  });
}

export function resumenLote(res, { onCambio } = {}) {
  if (!res || !res.total) {
    return h("div", { class: "pila" }, alerta("Sin clientes en ese grupo.", "warn"), diagnostico(res && res.diagnostico));
  }
  const gen = res.resultados.filter((r) => r.estado_proceso === "generado");
  const rev = gen.filter((r) => r.estado === "requiere_revision");
  const exi = res.resultados.filter((r) => r.estado_proceso === "existente");
  const omi = res.resultados.filter((r) => r.estado_proceso === "omitido");
  const motivos = {};
  for (const r of omi) motivos[r.motivo] = (motivos[r.motivo] || 0) + 1;
  const resultadoTexto = (r) => {
    if (r.estado_proceso === "omitido") return h("span", { class: "muted" }, `Omitido: ${r.motivo}`);
    if (r.estado_proceso === "existente") return [badge("Ya existía", "info"), " ", badgeEstado(r.estado)];
    return badgeEstado(r.estado);
  };
  return h("div", { class: "pila" },
    h("div", { class: "kpis" },
      kpi("Clientes procesados", num(res.total)), kpi("Borradores listos", num(gen.length - rev.length)),
      kpi("Requieren revisión", num(rev.length), { destacado: rev.length > 0 }), kpi("Ya tenían borrador", num(exi.length)),
      kpi("Omitidos", num(omi.length))),
    Object.keys(motivos).length ? alerta(Object.entries(motivos).map(([m, n]) => h("div", {}, `${n} omitido(s): ${m}`)), "info") : null,
    tabla([
      { titulo: "Cliente", valor: (r) => r.nombre },
      { titulo: "Resultado", valor: resultadoTexto },
      { titulo: "#", valor: (r) => (r.id ? `#${r.id}` : "—"), clase: "num" },
    ], res.resultados, { onFila: (r) => r.id && abrirMensaje(r.id, { onCambio }) }));
}

export function tareaLote(tarea, { onCambio } = {}) {
  return seguirTarea(tarea, {
    alTerminar: (res, zona) => {
      zona.append(resumenLote(res, { onCambio }));
      if (onCambio) onCambio();
    },
  });
}

export { chipsFiltros };
