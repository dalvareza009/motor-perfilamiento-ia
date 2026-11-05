// Perfiles públicos autorizados: quién autorizó, lectura, revisión de hechos, redes y vínculo con clientes.
import { get, post, put } from "../api.js";
import { vistaMensajes } from "./mensajes_prueba.js";
import { abrirCliente, dato } from "../componentes.js";
import { seguirTarea } from "../tarea.js?v=20261104lote2";
import {
  alerta, badge, cabecera, campo, cargando, conBoton, confirmar, errorCaja, fecha, h, icono, num, pestañas,
  segmentado, selector, tabla, toast, vacio,
} from "../ui.js";

let pestañaActiva = "hechos";

function mostrarLog(zona, r) {
  const lineas = (r.log || "").split("\n").filter(Boolean);
  toast(lineas[0] || "Listo.");
  zona.replaceChildren(lineas.length ? alerta(h("div", { class: "texto-pre" }, r.log), "ok") : "");
}

export async function render(cont) {
  const cuerpo = h("div", { class: "pila" });
  const definicion = [
    { id: "mensajes", texto: "Mensajes" },
    { id: "hechos", texto: "Revisión de hechos" },
    { id: "red", texto: "Seguidores e intereses" },
    { id: "linkedin", texto: "Redes" },
    { id: "vincular", texto: "Vincular y ofrecer" }, { id: "autorizados", texto: "Personas autorizadas" },
  ];
  const tabs = pestañas(definicion, pestañaActiva, (id) => { pestañaActiva = id; mostrar(); });
  const mostrar = () => cuerpo.replaceChildren(
    pestañaActiva === "mensajes" ? vistaMensajes()
      : pestañaActiva === "autorizados" ? vistaAutorizados()
        : pestañaActiva === "vincular" ? vistaVincular()
          : pestañaActiva === "linkedin" ? vistaLinkedin()
            : pestañaActiva === "red" ? vistaHechos(refrescarConteo, "red")
              : vistaHechos(refrescarConteo, "ficha"));
  async function refrescarConteo() {
    try {
      const [personas, mensajes] = await Promise.all([
        get("/api/perfiles/personas"),
        get("/api/mensajes-prueba").catch(() => []),
      ]);
      const pend = personas.reduce((a, p) => a + (p.pendientes || 0), 0);
      const pendRed = personas.reduce((a, p) => a + (p.pendientes_red || 0), 0);
      tabs.actualizar(definicion.map((d) => {
        if (d.id === "hechos") return { ...d, n: pend };
        if (d.id === "red") return { ...d, n: pendRed };
        if (d.id === "mensajes") return { ...d, n: mensajes.length };
        return d;
      }));
    } catch { /* el contador no es crítico */ }
  }
  cont.append(
    cabecera("Perfiles públicos", "Pega las URLs en Redes: el motor lee el nombre en cada red y registra a la persona. Los hechos extraídos quedan pendientes hasta tu revisión y solo los aprobados se usan en los borradores."),
    h("div", { class: "card pila" }, tabs.el, cuerpo));
  mostrar();
  refrescarConteo();
}

function tarjetaRecomendacion(r) {
  return h("div", { class: "item", style: { gridTemplateColumns: "1fr" } },
    h("div", { class: "item-cab" },
      h("strong", {}, r.producto),
      badge(`apoyado por ${r.publicaciones_que_apoyan} publicación(es)`, "ok"),
      badge(r.temas, "info")),
    h("div", {}, r.razones),
    h("div", { class: "pila-sm" }, (r.evidencias || []).map((e) => h("div", { class: "item-texto" },
      `[${e.tema}] ${e.extracto}`,
      e.url_publicacion ? h("div", {}, h("a", { href: e.url_publicacion, target: "_blank", rel: "noopener noreferrer", class: "pequeño" }, "Ver publicación")) : null))));
}

function mostrarRecomendaciones(res, zona) {
  if (!res) return;
  if (!res.ok) { zona.replaceChildren(alerta(res.motivo || "No se pudo extraer la actividad.", "warn")); return; }
  const g = res.guardado || {};
  const info = res.perfil_info || {};
  const ficha = info.nombre || info.titular || info.acerca ? h("div", { class: "card pila-sm" },
    h("strong", {}, info.nombre || "Perfil"),
    info.titular ? h("div", {}, info.titular) : null,
    info.bio ? h("div", {}, info.bio) : null,
    info.ubicacion ? h("div", { class: "muted pequeño" }, info.ubicacion) : null,
    info.experiencia ? h("div", {}, info.experiencia) : null,
    info.educacion ? h("div", {}, info.educacion) : null,
    info.estado_civil ? h("div", {}, info.estado_civil) : null,
    info.estado_laboral ? h("div", {}, info.estado_laboral) : null,
    info.estado_academico ? h("div", {}, info.estado_academico) : null,
    info.familia ? h("div", {}, info.familia) : null,
    info.edad ? h("div", {}, info.edad) : null,
    info.logros ? h("div", {}, info.logros) : null,
    info.resumen_red ? h("div", {}, info.resumen_red) : null,
    info.paginas_seguidas ? h("div", { class: "muted pequeño" }, info.paginas_seguidas) : null,
    info.interacciones ? h("div", { class: "muted pequeño" }, info.interacciones) : null,
    info.en_x_desde ? h("div", { class: "muted pequeño" }, info.en_x_desde) : null,
    info.seguidores ? h("div", { class: "muted pequeño" }, `${info.seguidores} amigos/seguidores`) : null,
    info.privado ? alerta("La cuenta es privada para esta sesión: se guardó la ficha visible y no se leyeron publicaciones.", "warn") : null,
    res.temas_del_perfil && Object.keys(res.temas_del_perfil).length
      ? h("div", {}, `Temas desde la ficha: ${Object.entries(res.temas_del_perfil).map(([t, n]) => `${t} (${n})`).join(", ")}`) : null) : null;
  const resumen = res.solo_perfil
    ? `Se leyó la ficha personal. Quedó en la base: ${num(g.hechos_nuevos)} hecho(s) nuevo(s), ${num(g.hechos_actualizados)} actualizado(s)${g.productos_sugeridos && g.productos_sugeridos.length ? `, productos: ${g.productos_sugeridos.join(", ")}` : ""}${info.resumen_red ? `. ${info.resumen_red}` : ""}. Revisa la ficha en «Revisión de hechos» y las listas en «Seguidores e intereses».`
    : `${num(res.publicaciones)} publicación(es) del último año analizadas${res.descartadas_antiguas ? `, ${num(res.descartadas_antiguas)} antiguas descartadas` : ""}${res.omitidas_sensibles ? `, ${num(res.omitidas_sensibles)} omitida(s) por tema sensible` : ""}. Quedó en la base: ${num(g.hechos_nuevos)} hecho(s) nuevo(s), ${num(g.hechos_actualizados)} actualizado(s)${g.productos_sugeridos && g.productos_sugeridos.length ? `, productos: ${g.productos_sugeridos.join(", ")}` : ""}${info.resumen_red ? `. ${info.resumen_red}` : ""}. Revisa la ficha en «Revisión de hechos» y las listas en «Seguidores e intereses».`;
  zona.replaceChildren(h("div", { class: "pila" },
    ficha,
    alerta(resumen, "ok"),
    (res.mensajes || []).length ? h("div", { class: "pila" },
      h("h3", {}, "Tres mensajes de prueba"),
      h("a", { href: "#/mensajes-prueba", class: "pequeño" }, "Verlos también en Mensajes"),
      ...(res.mensajes || []).map((m) => h("div", { class: "card pila-sm" },
        h("div", { class: "item-cab" }, h("strong", {}, `Opción ${m.opcion}`), badge(m.estado === "borrador" ? "Listo para revisar" : "Revisar", m.estado === "borrador" ? "ok" : "warn")),
        h("div", { class: "mensaje-cuerpo whatsapp" }, m.cuerpo)))) : null,
    res.solo_perfil ? null
      : res.publicaciones === 0 && !(res.recomendaciones || []).length
        ? vacio("No hay actividad del último año que analizar en este perfil.", "check")
        : (res.recomendaciones || []).length ? res.recomendaciones.map(tarjetaRecomendacion)
          : vacio("Ni la ficha ni la actividad del último año mencionan temas del catálogo: no hay recomendación que hacer.", "check")));
}

function mostrarLectura(res, zona) {
  const lista = (res && res.resultados) || [];
  if (!lista.length) {
    zona.replaceChildren(alerta("No se leyó ningún perfil. Pega las URLs en Redes (LinkedIn, Facebook, Instagram o X), una por línea.", "warn"));
    return;
  }
  zona.replaceChildren(h("div", { class: "pila" }, lista.map((item) => {
    const caja = h("div", { class: "pila" });
    mostrarRecomendaciones(item, caja);
    return h("div", { class: "pila" },
      h("h3", {}, `${item.nombre || "Perfil"}${item.red ? ` · ${item.red}` : ""}`),
      item.perfil ? h("a", { href: item.perfil, target: "_blank", rel: "noopener noreferrer", class: "pequeño" }, item.perfil) : null,
      caja);
  })));
}

function vigilarLogin(idTarea, base = "/api/linkedin/actividad") {
  const zona = h("div");
  const reloj = setInterval(async () => {
    try {
      const t = await get(`/api/tareas/${idTarea}`);
      if (t.estado !== "en_curso") { clearInterval(reloj); zona.replaceChildren(); return; }
      const esperas = await get(`${base}/esperas`);
      if (!esperas.some((e) => e.id === idTarea) || zona.firstChild) return;
      const bYa = h("button", { class: "btn btn-sm btn-primario" }, icono("check"), "Ya inicié sesión, continuar");
      const bNo = h("button", { class: "btn btn-sm btn-peligro-suave" }, icono("x"), "Cancelar");
      bYa.addEventListener("click", async () => { await post(`${base}/${idTarea}/continuar`, {}); zona.replaceChildren(alerta("Comprobando la sesión…", "info")); setTimeout(() => zona.replaceChildren(), 2500); });
      bNo.addEventListener("click", async () => { await post(`${base}/${idTarea}/cancelar`, {}); clearInterval(reloj); zona.replaceChildren(); });
      zona.replaceChildren(alerta([h("strong", {}, "Chrome quedó abierto esperando tu inicio de sesión. "),
        "Entra con tu cuenta en esa ventana (contraseña, código o captcha si lo pide) y luego pulsa continuar. El bot no se cierra.",
        h("div", { class: "fila", style: { marginTop: "8px" } }, bYa, bNo)], "warn"));
    } catch { /* reintenta en el siguiente tick */ }
  }, 2000);
  return zona;
}

// ------------------------------------------------------------------ publicaciones de LinkedIn
function vistaLinkedin() {
  let estadoF = "pendiente";
  const seleccion = new Set();
  const zona = h("div", { class: "pila" }, cargando());
  const zonaLog = h("div");
  const zonaTareas = h("div", { class: "pila" });
  const contador = h("span", { class: "muted" });
  const bAprobar = h("button", { class: "btn btn-sm btn-primario", disabled: true }, icono("check"), "Aprobar seleccionados");
  const bDescartar = h("button", { class: "btn btn-sm btn-peligro-suave", disabled: true }, icono("x"), "Descartar seleccionados");
  let total = 0;

  const actualizarSel = () => {
    contador.textContent = seleccion.size ? `${seleccion.size} seleccionado(s)` : `${num(total)} interés(es)`;
    bAprobar.disabled = bDescartar.disabled = !seleccion.size;
  };

  async function operar(boton, ruta, datos) {
    const r = await conBoton(boton, () => post(ruta, datos));
    if (!r) return;
    mostrarLog(zonaLog, r);
    await cargar();
  }
  bAprobar.addEventListener("click", () => operar(bAprobar, "/api/linkedin/intereses/aprobar", { ids: [...seleccion] }));
  bDescartar.addEventListener("click", () => operar(bDescartar, "/api/linkedin/intereses/descartar", { ids: [...seleccion] }));

  function item(x) {
    const pendiente = !x.activo && !x.descartado;
    const fila = h("div", { class: "item" });
    const check = h("input", { type: "checkbox", disabled: !pendiente });
    check.addEventListener("change", () => {
      if (check.checked) seleccion.add(x.id_interes); else seleccion.delete(x.id_interes);
      fila.classList.toggle("sel", check.checked);
      actualizarSel();
    });
    const estadoB = x.activo ? badge("Aprobado", "ok") : x.descartado ? badge("Descartado") : badge("Pendiente", "warn");
    const acciones = pendiente ? [
      h("button", { class: "btn btn-sm btn-ok", onclick: (e) => operar(e.currentTarget, "/api/linkedin/intereses/aprobar", { ids: [x.id_interes] }) }, icono("check"), "Aprobar"),
      h("button", { class: "btn btn-sm btn-peligro-suave", onclick: (e) => operar(e.currentTarget, "/api/linkedin/intereses/descartar", { ids: [x.id_interes] }) }, icono("x"), "Descartar"),
    ] : null;
    fila.append(h("div", {}, check), h("div", { class: "pila-sm" },
      h("div", { class: "item-cab" },
        h("strong", {}, x.producto), badge(x.tema, "info"),
        h("span", { class: "muted pequeño" }, `${x.nombre}${x.clave_cliente ? ` · clave ${x.clave_cliente}` : ""} · #${x.id_interes}`),
        h("span", { class: "espaciador" }), estadoB),
      h("div", {}, x.razon),
      h("div", { class: "item-texto" }, x.texto),
      h("div", { class: "fila" },
        h("a", { href: x.fuente_url, target: "_blank", rel: "noopener noreferrer", class: "pequeño fila", style: { gap: "4px" } }, icono("external"), "Perfil"),
        h("span", { class: "muted pequeño" }, x.tiempo || fecha(x.fecha_actualizacion)),
        h("span", { class: "espaciador" }), acciones)));
    return fila;
  }

  async function cargar() {
    zona.replaceChildren(cargando());
    seleccion.clear();
    try {
      const filas = await get(`/api/linkedin/intereses?estado=${estadoF}`);
      total = filas.length;
      zona.replaceChildren(filas.length ? h("div", { class: "items" }, filas.map(item))
        : vacio(estadoF === "pendiente" ? "No hay intereses por revisar." : "No hay intereses en este estado.", "check"));
    } catch (e) {
      zona.replaceChildren(errorCaja(e, cargar));
    }
    actualizarSel();
  }

  const bLeer = h("button", { class: "btn btn-primario" }, icono("play"), "Leer perfiles autorizados");
  bLeer.addEventListener("click", async () => {
    const r = await conBoton(bLeer, () => post("/api/linkedin/leer", { nombres: [] }));
    if (r) zonaTareas.prepend(seguirTarea(r.tarea, { alTerminar: () => cargar() }));
  });

  // ---------------- Actividad con mi sesión (cookies / perfil de Chrome)
  const urlSesion = h("input", { type: "text", placeholder: "https://www.linkedin.com/in/…" });
  const topePosts = (el) => {
    const n = parseInt(el && el.value, 10);
    return Number.isFinite(n) ? Math.min(10, Math.max(1, n)) : 10;
  };
  const maxSesion = h("input", { type: "number", value: "10", min: "1", max: "10", style: { width: "90px" } });
  const bExtraer = h("button", { class: "btn btn-primario" }, icono("play"), "Extraer actividad y recomendar");
  const zonaSesion = h("div", { class: "pila" });

  function lanzarSesion(tarea) {
    zonaSesion.prepend(vigilarLogin(tarea.id),
      seguirTarea(tarea, { alTerminar: (res, z) => mostrarRecomendaciones(res, z) }));
  }

  bExtraer.addEventListener("click", async () => {
    const url = urlSesion.value.trim();
    if (!url) { toast("Pega la URL del perfil de LinkedIn.", "error"); urlSesion.focus(); return; }
    const r = await conBoton(bExtraer, () => post("/api/linkedin/actividad", { url, max_posts: topePosts(maxSesion) }));
    if (r) lanzarSesion(r.tarea);
  });
  // Si ya había una extracción corriendo (p. ej. cambiaste de pestaña), se retoma.
  const loteUrls = h("textarea", { rows: 8, placeholder: "https://www.instagram.com/usuario/\nhttps://x.com/usuario\nhttps://www.facebook.com/usuario\nhttps://www.linkedin.com/in/usuario/\nUna URL por línea, entre 20 y 50." });
  const maxLote = h("input", { type: "number", value: "10", min: "1", max: "10", style: { width: "90px" } });
  const bLote = h("button", { class: "btn btn-primario" }, icono("play"), "Extraer lote");
  const zonaLote = h("div", { class: "pila" });
  function lanzarLote(tarea) {
    zonaLote.prepend(vigilarLogin(tarea.id),
      seguirTarea(tarea, { alTerminar: (res, z) => mostrarLectura(res, z) }));
  }
  bLote.addEventListener("click", async () => {
    const urls = loteUrls.value.split(/\n/).map((u) => u.trim()).filter(Boolean);
    if (!urls.length) { toast("Pega al menos una URL, una por línea.", "error"); loteUrls.focus(); return; }
    if (urls.length > 50) { toast("El lote admite como máximo 50 perfiles.", "error"); return; }
    const r = await conBoton(bLote, async () => {
      let listo = null;
      try { listo = await get("/api/perfiles/lote"); } catch { listo = null; }
      if (!listo || listo.solo_urls !== true) {
        throw new Error(
          "El servidor que está corriendo es el viejo y se va a Personas autorizadas. "
          + "Cierra Chrome del motor, en la terminal Ctrl+C, luego: python -m app.api"
        );
      }
      const res = await post("/api/perfiles/lote", { urls, max_posts: topePosts(maxLote) });
      const tarea = res && res.tarea;
      if (!res || res.solo_urls !== true || !tarea || tarea.tipo !== "ingesta_lote") {
        throw new Error("El servidor no tomó las URLs pegadas. Reinicia con: python -m app.api");
      }
      if (/autorizad/i.test(tarea.descripcion || "")) {
        throw new Error("Se iba a leer Personas autorizadas. Se canceló. Reinicia el motor y vuelve a extraer el lote.");
      }
      return res;
    });
    if (r && r.tarea) {
      toast(`Lote: ${ (r.urls || urls).length } URL(s) pegadas. No se leen autorizados.`);
      lanzarLote(r.tarea);
    }
  });
  get("/api/tareas").then((ts) => ts.filter((t) => t.tipo === "ingesta_linkedin_sesion" && t.estado === "en_curso")
    .forEach(lanzarSesion)).catch(() => {});
  get("/api/tareas").then((ts) => ts.filter((t) => t.tipo === "ingesta_lote" && t.estado === "en_curso")
    .forEach(lanzarLote)).catch(() => {});

  // ---------------- Facebook con mi sesión (mismo criterio)
  const urlFb = h("input", { type: "text", placeholder: "https://www.facebook.com/usuario" });
  const maxFb = h("input", { type: "number", value: "10", min: "1", max: "10", style: { width: "90px" } });
  const bExtraerFb = h("button", { class: "btn btn-primario" }, icono("play"), "Extraer de Facebook");
  const zonaFb = h("div", { class: "pila" });
  function lanzarFb(tarea) {
    zonaFb.prepend(vigilarLogin(tarea.id, "/api/facebook/actividad"),
      seguirTarea(tarea, { alTerminar: (res, z) => mostrarRecomendaciones(res, z) }));
  }
  bExtraerFb.addEventListener("click", async () => {
    const url = urlFb.value.trim();
    if (!url) { toast("Pega la URL del perfil de Facebook.", "error"); urlFb.focus(); return; }
    const r = await conBoton(bExtraerFb, () => post("/api/facebook/actividad", { url, max_posts: topePosts(maxFb) }));
    if (r) lanzarFb(r.tarea);
  });
  get("/api/tareas").then((ts) => ts.filter((t) => t.tipo === "extraccion_facebook" && t.estado === "en_curso")
    .forEach(lanzarFb)).catch(() => {});

  // ---------------- Instagram con mi sesión (mismo criterio)
  const urlIg = h("input", { type: "text", placeholder: "https://www.instagram.com/usuario/" });
  const maxIg = h("input", { type: "number", value: "10", min: "1", max: "10", style: { width: "90px" } });
  const bExtraerIg = h("button", { class: "btn btn-primario" }, icono("play"), "Extraer de Instagram y recomendar");
  const zonaIg = h("div", { class: "pila" });
  function lanzarIg(tarea) {
    zonaIg.prepend(vigilarLogin(tarea.id, "/api/instagram/actividad"),
      seguirTarea(tarea, { alTerminar: (res, z) => mostrarRecomendaciones(res, z) }));
  }
  bExtraerIg.addEventListener("click", async () => {
    const url = urlIg.value.trim();
    if (!url) { toast("Pega la URL del perfil de Instagram.", "error"); urlIg.focus(); return; }
    const r = await conBoton(bExtraerIg, () => post("/api/instagram/actividad", { url, max_posts: topePosts(maxIg) }));
    if (r) lanzarIg(r.tarea);
  });
  get("/api/tareas").then((ts) => ts.filter((t) => t.tipo === "extraccion_instagram" && t.estado === "en_curso")
    .forEach(lanzarIg)).catch(() => {});

  // ---------------- X con mi sesión (mismo criterio)
  const urlX = h("input", { type: "text", placeholder: "https://x.com/usuario" });
  const maxX = h("input", { type: "number", value: "10", min: "1", max: "10", style: { width: "90px" } });
  const bExtraerX = h("button", { class: "btn btn-primario" }, icono("play"), "Extraer de X y recomendar");
  const zonaX = h("div", { class: "pila" });
  function lanzarX(tarea) {
    zonaX.prepend(vigilarLogin(tarea.id, "/api/x/actividad"),
      seguirTarea(tarea, { alTerminar: (res, z) => mostrarRecomendaciones(res, z) }));
  }
  bExtraerX.addEventListener("click", async () => {
    const url = urlX.value.trim();
    if (!url) { toast("Pega la URL del perfil de X.", "error"); urlX.focus(); return; }
    const r = await conBoton(bExtraerX, () => post("/api/x/actividad", { url, max_posts: topePosts(maxX) }));
    if (r) lanzarX(r.tarea);
  });
  get("/api/tareas").then((ts) => ts.filter((t) => t.tipo === "extraccion_x" && t.estado === "en_curso")
    .forEach(lanzarX)).catch(() => {});

  cargar();
  return h("div", { class: "pila" },
    h("div", { class: "card pila" },
      h("h3", {}, "Lote de perfiles (20 a 50)"),
      alerta("Extraer lote lee únicamente las URLs que pegas (Instagram, Facebook, X o LinkedIn). Si hay una lectura de Personas autorizadas en curso, la detiene. El nombre sale de cada red y se registra al terminar. Publicaciones: de 1 a 10.", "info"),
      campo("URLs", loteUrls),
      h("div", { class: "fila", style: { alignItems: "flex-end" } },
        campo("Publicaciones a analizar (1 a 10)", maxLote),
        bLote),
      zonaLote),
    h("div", { class: "card pila" },
      h("h3", {}, "Actividad con mi sesión (cookies)"),
      alerta("Usa tu sesión guardada (perfil de Chrome + cookies de este equipo) y no se cierra si LinkedIn pide entrar: Chrome queda abierto, inicias sesión tú y pulsas «Ya inicié sesión, continuar». Al terminar verás aquí las recomendaciones con la publicación que las respalda. Solo tu propia cuenta.", "info"),
      h("div", { class: "fila", style: { alignItems: "flex-end" } },
        h("div", { style: { flex: "1", minWidth: "260px" } }, campo("Perfil de LinkedIn", urlSesion)),
        campo("Publicaciones (1 a 10)", maxSesion),
        bExtraer),
      zonaSesion),
    h("div", { class: "card pila" },
      h("h3", {}, "Facebook con mi sesión"),
      alerta("Pega la URL del perfil. Se lee el nombre, la presentación, seguidores, páginas que sigue, grupos, publicaciones y lo que compartió. Si Facebook pide entrar, Chrome queda abierto: inicia sesión y pulsa «Ya inicié sesión, continuar».", "info"),
      h("div", { class: "fila", style: { alignItems: "flex-end" } },
        h("div", { style: { flex: "1", minWidth: "260px" } }, campo("Perfil de Facebook", urlFb)),
        campo("Publicaciones (1 a 10)", maxFb),
        bExtraerFb),
      zonaFb),
    h("div", { class: "card pila" },
      h("h3", {}, "Instagram con mi sesión"),
      alerta("Pega la URL del perfil. Se lee el nombre, la bio, seguidores, a quién sigue, las publicaciones y el apartado de reposts. Si la cuenta es privada, se guarda lo visible. Si Instagram pide entrar, Chrome queda abierto: inicia sesión y pulsa «Ya inicié sesión, continuar».", "info"),
      h("div", { class: "fila", style: { alignItems: "flex-end" } },
        h("div", { style: { flex: "1", minWidth: "260px" } }, campo("Perfil de Instagram", urlIg)),
        campo("Publicaciones (1 a 10)", maxIg),
        bExtraerIg),
      zonaIg),
    h("div", { class: "card pila" },
      h("h3", {}, "X con mi sesión"),
      alerta("Pega la URL del perfil. Se lee el nombre, la bio, seguidores, following, publicaciones, respuestas, logros y republicaciones. Si X pide entrar, usa la ventana de Chrome que se abre. Cuando ya estés dentro, pulsa «Ya inicié sesión, continuar».", "info"),
      h("div", { class: "fila", style: { alignItems: "flex-end" } },
        h("div", { style: { flex: "1", minWidth: "260px" } }, campo("Perfil de X", urlX)),
        campo("Publicaciones (1 a 10)", maxX),
        bExtraerX),
      zonaX),
    alerta("Se abre el perfil público. El nombre se lee de LinkedIn y la persona queda registrada. Si LinkedIn pide iniciar sesión, esa página no se lee. Política y religión se descartan y no se guardan; el salario sí cuenta, como señal de ingresos. El interés aprobado pasa al perfil; el resto no.", "info"),
    h("div", { class: "fila" }, bLeer),
    zonaTareas,
    segmentado([{ valor: "pendiente", texto: "Pendientes" }, { valor: "aprobado", texto: "Aprobados" }, { valor: "descartado", texto: "Descartados" }],
      estadoF, (v) => { estadoF = v; cargar(); }),
    h("div", { class: "barra-acciones" }, contador, h("span", { class: "espaciador" }), bDescartar, bAprobar),
    zonaLog, zona);
}

// ------------------------------------------------------------------ revisión de hechos
function vistaHechos(alCambiar, grupo = "ficha") {
  const esRed = grupo === "red";
  let estadoF = "pendiente";
  const persona = selector([{ valor: "", texto: "Todas las personas" }], "");
  const seleccion = new Set();
  const zona = h("div", { class: "pila" }, cargando());
  const zonaLog = h("div");
  const contador = h("span", { class: "muted" });
  const bAprobar = h("button", { class: "btn btn-sm btn-primario", disabled: true }, icono("check"), "Aprobar seleccionados");
  const bDescartar = h("button", { class: "btn btn-sm btn-peligro-suave", disabled: true }, icono("x"), "Descartar seleccionados");
  const bTodos = h("button", { class: "btn btn-sm" }, icono("check"), "Aprobar todos los pendientes");
  let total = 0;

  const actualizarSel = () => {
    contador.textContent = seleccion.size ? `${seleccion.size} seleccionado(s)` : `${num(total)} hecho(s)`;
    bAprobar.disabled = bDescartar.disabled = !seleccion.size;
  };

  get("/api/perfiles/personas").then((ps) => {
    const actual = persona.value;
    persona.replaceChildren(h("option", { value: "" }, "Todas las personas"),
      ...ps.map((p) => h("option", { value: p.nombre }, `${p.nombre}${p.pendientes ? ` (${p.pendientes} por revisar)` : ""}`)));
    persona.value = actual;
  }).catch(() => {});

  async function operar(boton, ruta, datos) {
    const r = await conBoton(boton, () => post(ruta, datos));
    if (!r) return;
    mostrarLog(zonaLog, r);
    await cargar();
    alCambiar();
  }
  bAprobar.addEventListener("click", () => operar(bAprobar, "/api/perfiles/hechos/aprobar", { ids: [...seleccion] }));
  bDescartar.addEventListener("click", () => operar(bDescartar, "/api/perfiles/hechos/descartar", { ids: [...seleccion] }));
  bTodos.addEventListener("click", async () => {
    const ok = await confirmar("¿Aprobar todos los pendientes?",
      esRed
        ? "Se aprobarán todos los seguidores e intereses pendientes (no los hechos de la ficha)."
        : "Se aprobarán todos los hechos de ficha pendientes (no los seguidores e intereses).",
      { boton: "Aprobar todos" });
    if (ok) operar(bTodos, "/api/perfiles/hechos/aprobar", { todos: true, grupo });
  });

  function item(x) {
    const pendiente = !x.activo && !x.descartado;
    const fila = h("div", { class: "item" });
    const check = h("input", { type: "checkbox", disabled: !pendiente });
    check.addEventListener("change", () => {
      if (check.checked) seleccion.add(x.id_hecho); else seleccion.delete(x.id_hecho);
      fila.classList.toggle("sel", check.checked);
      actualizarSel();
    });
    const estadoB = x.activo ? badge("Aprobado", "ok") : x.descartado ? badge("Descartado") : badge("Pendiente", "warn");
    const acciones = pendiente ? [
      h("button", { class: "btn btn-sm btn-ok", onclick: (e) => operar(e.currentTarget, "/api/perfiles/hechos/aprobar", { ids: [x.id_hecho] }) }, icono("check"), "Aprobar"),
      h("button", { class: "btn btn-sm btn-peligro-suave", onclick: (e) => operar(e.currentTarget, "/api/perfiles/hechos/descartar", { ids: [x.id_hecho] }) }, icono("x"), "Descartar"),
    ] : null;
    fila.append(h("div", {}, check), h("div", { class: "pila-sm" },
      h("div", { class: "item-cab" },
        h("strong", {}, x.titulo), badge(x.categoria, x.categoria === "Producto sugerido" ? "primario" : x.categoria === "Contacto" ? "warn" : "info"),
        badge(x.red), h("span", { class: "muted pequeño" }, `${x.nombre}${x.clave_cliente ? ` · clave ${x.clave_cliente}` : " · sin vincular"} · #${x.id_hecho}`),
        h("span", { class: "espaciador" }), estadoB),
      h("div", { class: "item-texto" }, x.contenido),
      h("div", { class: "fila" },
        x.fuente_url ? h("a", { href: x.fuente_url, target: "_blank", rel: "noopener noreferrer", class: "pequeño fila", style: { gap: "4px" } }, icono("external"), "Perfil") : null,
        h("span", { class: "muted pequeño" }, fecha(x.fecha_actualizacion)), h("span", { class: "espaciador" }), acciones)));
    return fila;
  }

  async function cargar() {
    zona.replaceChildren(cargando());
    seleccion.clear();
    try {
      const filas = await post("/api/perfiles/hechos/lista", {
        nombre: persona.value, estado: estadoF, grupo, limite: esRed ? 1000 : 500,
      });
      const catsRed = new Set(["Seguidor", "Sigue a", "Repost"]);
      const visibles = (filas || []).filter((x) => esRed ? catsRed.has(x.categoria) : !catsRed.has(x.categoria));
      total = visibles.length;
      zona.replaceChildren(visibles.length ? h("div", { class: "items" }, visibles.map(item))
        : vacio(estadoF === "pendiente"
          ? (esRed
            ? "No hay seguidores, cuentas seguidas ni reposts por revisar. Extrae un perfil desde «Redes»."
            : "No hay hechos por revisar. Extrae perfiles desde «Redes».")
          : "No hay hechos en este estado.", "check"));
    } catch (e) {
      zona.replaceChildren(errorCaja(e, cargar));
    }
    actualizarSel();
  }
  persona.addEventListener("change", cargar);
  cargar();

  return h("div", { class: "pila" },
    h("div", { class: "fila", style: { alignItems: "flex-end" } },
      h("div", { style: { minWidth: "260px" } }, campo("Persona", persona)),
      segmentado([{ valor: "pendiente", texto: "Pendientes" }, { valor: "aprobado", texto: "Aprobados" }, { valor: "descartado", texto: "Descartados" }, { valor: "todos", texto: "Todos" }],
        estadoF, (v) => { estadoF = v; cargar(); })),
    alerta(esRed
      ? "Solo aparece quién le sigue, a quién o a qué páginas/grupos sigue, y de quién hace repost (X, Instagram, Facebook y LinkedIn). Aprueba cada uno para usarlo como interés."
      : "Revisa que cada hecho sea explícito y correcto. Un «Producto sugerido» es solo una pista para el asesor; el contacto (correo/celular) sirve para completar la ficha del cliente. Seguidores, páginas que sigue y reposts van en la pestaña de al lado.", "info"),
    h("div", { class: "barra-acciones" }, contador, h("span", { class: "espaciador" }), bTodos, bDescartar, bAprobar),
    zonaLog, zona);
}

// ------------------------------------------------------------------ vincular, completar, incorporar
function vistaVincular() {
  const lista = h("div", {}, cargando());
  const detalle = h("div", { class: "detalle" }, h("div", { class: "card" }, vacio("Elige una persona para ver su oferta y vincularla con un cliente.", "idcard")));
  let elegido = null;

  async function cargarLista() {
    try {
      const ps = await get("/api/perfiles/personas");
      lista.replaceChildren(tabla([
        { titulo: "Persona", valor: (p) => [h("strong", {}, p.nombre), h("span", { class: "celda-sub" }, p.redes || "")] },
        { titulo: "Cliente", valor: (p) => (p.clave_cliente ? badge(p.clave_cliente, "ok") : badge("Sin vincular", "warn")) },
        { titulo: "Aprobados", valor: (p) => num(p.aprobados), clase: "num" },
        { titulo: "Por revisar", valor: (p) => num(p.pendientes), clase: "num" },
      ], ps, { onFila: (p) => abrir(p.nombre), seleccion: (p) => p.nombre === elegido, vacioTexto: "Aún no hay perfiles leídos." }));
    } catch (e) {
      lista.replaceChildren(errorCaja(e, cargarLista));
    }
  }

  async function abrir(nombre) {
    elegido = nombre;
    lista.querySelectorAll("tbody tr").forEach((tr) => tr.classList.toggle("sel", tr.querySelector("strong")?.textContent === nombre));
    detalle.replaceChildren(h("div", { class: "card" }, cargando()));
    try {
      detalle.replaceChildren(fichaPersona(await post("/api/perfiles/persona", { nombre }), () => { cargarLista(); abrir(nombre); }));
    } catch (e) {
      detalle.replaceChildren(errorCaja(e, () => abrir(nombre)));
    }
  }

  cargarLista();
  return h("div", { class: "dividido" }, lista, detalle);
}

function fichaPersona(d, refrescar) {
  const zonaLog = h("div");
  const aprobados = d.hechos.filter((x) => x.activo);
  const datos = d.datos || {};

  async function operar(boton, ruta, cuerpo) {
    const r = await conBoton(boton, () => post(ruta, cuerpo));
    if (!r) return;
    mostrarLog(zonaLog, r);
    setTimeout(refrescar, 600);
  }

  const accionesCliente = (c) => h("div", { class: "fila", style: { gap: "4px" } },
    c.clave_cliente !== d.clave_cliente
      ? h("button", { class: "btn btn-sm", title: "Escribe la clave del cliente en todos los hechos de esta persona", onclick: (e) => operar(e.currentTarget, "/api/perfiles/vincular", { nombre: d.nombre, clave: c.clave_cliente }) }, icono("link"), "Vincular")
      : badge("Vinculado", "ok"),
    h("button", { class: "btn btn-sm", title: "Llena campos vacíos del cliente (correo, celular, ciudad…) con los hechos aprobados. No pisa datos existentes.", onclick: (e) => operar(e.currentTarget, "/api/perfiles/completar", { nombre: d.nombre, clave: c.clave_cliente }) }, icono("plus"), "Completar vacíos"),
    h("button", { class: "btn btn-sm btn-fantasma", title: "Abrir ficha", onclick: () => abrirCliente(c.clave_cliente) }, icono("eye")));

  const producto = h("input", { type: "text", value: datos.producto_interes || "", placeholder: "p. ej. Seguro educativo" });
  const bIncorporar = h("button", { class: "btn btn-primario" }, icono("plus"), "Incorporar como prospecto");
  bIncorporar.addEventListener("click", async () => {
    const ok = await confirmar("¿Crear el cliente?", `Se creará a ${d.nombre} en la tabla de clientes como «Prospecto» con los datos aprobados${producto.value.trim() ? ` y producto «${producto.value.trim()}»` : ""}.`, { boton: "Crear cliente" });
    if (ok) operar(bIncorporar, "/api/perfiles/incorporar", { nombre: d.nombre, producto: producto.value.trim() });
  });

  const canal = d.vinculado ? (d.vinculado.tiene_celular ? "WhatsApp" : d.vinculado.tiene_correo ? "correo" : null) : null;

  return h("div", { class: "pila" },
    h("div", { class: "card pila" },
      h("div", { class: "fila" }, h("h2", { style: { flex: "1" } }, d.nombre),
        d.clave_cliente ? badge(`clave ${d.clave_cliente}`, "ok") : badge("Sin vincular", "warn")),
      aprobados.length ? null : alerta("Esta persona no tiene hechos aprobados todavía. Apruébalos en «Revisión de hechos» antes de vincular o completar.", "warn"),
      h("h3", {}, "Lo que dicen los hechos aprobados"),
      h("div", { class: "datos-grid" },
        dato("Producto para ofrecer", datos.producto_interes || "Sin sugerencia aprobada"), dato("Ciudad", datos.ciudad),
        dato("Profesión", datos.profesion), dato("Estudios", datos.universidad), dato("Correo", datos.correo), dato("Celular", datos.celular)),
      d.vinculado
        ? alerta([h("strong", {}, `Vinculado a ${d.vinculado.nombre}. `),
          canal ? `El asesor puede pedir: «mensaje de ${canal} para ${d.vinculado.nombre}».` : "El cliente no tiene correo ni celular válido: el asesor lo encuentra pero no puede armar el borrador. Usa «Completar vacíos» si el perfil trae contacto."], canal ? "ok" : "warn")
        : null),
    zonaLog,
    h("div", { class: "card pila-sm" },
      h("h3", {}, "Clientes que coinciden"),
      d.clientes.length
        ? tabla([
          { titulo: "Cliente", valor: (c) => [h("strong", {}, c.nombre), h("span", { class: "celda-sub mono" }, c.clave_cliente)] },
          { titulo: "Producto", valor: (c) => c.producto_interes || "—" },
          { titulo: "Contacto", valor: (c) => [c.tiene_correo ? "correo" : null, c.tiene_celular ? "celular" : null].filter(Boolean).join(" · ") || "sin contacto" },
          { titulo: "", valor: accionesCliente },
        ], d.clientes)
        : h("div", { class: "pila-sm" },
          h("p", { class: "muted" }, "Ese nombre no está en clientes. Puedes crearlo como prospecto con los datos aprobados."),
          h("div", { class: "fila", style: { alignItems: "flex-end" } }, h("div", { style: { flex: "1", minWidth: "220px" } }, campo("Producto de interés", producto)), bIncorporar))),
    h("details", { class: "card" }, h("summary", {}, `Hechos (${d.hechos.length})`),
      h("div", { class: "items", style: { marginTop: "10px" } }, d.hechos.map((x) => h("div", { class: "item", style: { gridTemplateColumns: "1fr" } },
        h("div", {}, h("div", { class: "item-cab" }, badge(x.categoria, "info"), h("span", { class: "muted pequeño" }, x.red), h("span", { class: "espaciador" }),
          x.activo ? badge("Aprobado", "ok") : x.descartado ? badge("Descartado") : badge("Pendiente", "warn")),
        h("div", { class: "item-texto" }, x.contenido)))))));
}

// ------------------------------------------------------------------ personas autorizadas (data/perfiles_autorizados.json)
function vistaAutorizados() {
  let personas = [];
  let sucio = false;
  const zona = h("div", { class: "pila" }, cargando());
  const zonaAvisos = h("div");
  const zonaTareas = h("div", { class: "pila" });
  const bGuardar = h("button", { class: "btn btn-primario" }, icono("save"), "Guardar cambios");
  const bLeerTodos = h("button", { class: "btn" }, icono("play"), "Leer perfiles de todos");

  const marcar = () => { sucio = true; };
  const pintarAvisos = (avisos) => zonaAvisos.replaceChildren(avisos && avisos.length
    ? alerta([h("strong", {}, "Revisa antes de leer:"), h("ul", {}, avisos.map((a) => h("li", {}, a)))], "warn") : "");

  function leer(boton, nombres) {
    conBoton(boton, async () => {
      if (sucio) {
        const guardado = await put("/api/perfiles/autorizados", { personas });
        sucio = false;
        pintarAvisos(guardado.avisos);
        toast("Guardé la persona y empecé la lectura.");
      }
      return post("/api/perfiles/ingesta", nombres.length ? { nombres } : { todos: true });
    }).then((r) => {
      if (r) zonaTareas.prepend(vigilarLogin(r.tarea.id), seguirTarea(r.tarea, { alTerminar: (res, z) => mostrarLectura(res, z) }));
    });
  }

  function tarjeta(p, i) {
    const urls = h("div", { class: "pila-sm" });
    const pintarUrls = () => urls.replaceChildren(...p.urls.map((u, j) => h("div", { class: "fila" },
      h("input", { type: "text", value: u, placeholder: "https://www.linkedin.com/in/…, facebook, instagram o x.com", style: { flex: "1" }, oninput: (e) => { p.urls[j] = e.target.value; marcar(); } }),
      h("button", { class: "btn btn-fantasma btn-icono", title: "Quitar URL", onclick: () => { p.urls.splice(j, 1); marcar(); pintarUrls(); } }, icono("x")))),
    h("button", { class: "btn btn-sm btn-fantasma", style: { alignSelf: "flex-start" }, onclick: () => { p.urls.push(""); marcar(); pintarUrls(); } }, icono("plus"), "Agregar URL"));
    pintarUrls();
    const bLeer = h("button", { class: "btn btn-sm" }, icono("play"), "Leer solo esta persona");
    bLeer.addEventListener("click", () => leer(bLeer, [p.nombre]));
    return h("div", { class: "card pila-sm" },
      h("div", { class: "filtros-grid" },
        campo("Nombre", h("input", { type: "text", value: p.nombre, oninput: (e) => { p.nombre = e.target.value; marcar(); } })),
        campo("Clave de cliente (opcional)", h("input", { type: "text", value: p.clave_cliente, oninput: (e) => { p.clave_cliente = e.target.value; marcar(); } }))),
      h("label", { class: "check" }, h("input", { type: "checkbox", checked: p.autorizado, onchange: (e) => { p.autorizado = e.target.checked; marcar(); } }), "La persona autorizó leer su perfil público"),
      campo("Texto de la autorización", h("textarea", { rows: 2, oninput: (e) => { p.autorizacion = e.target.value; marcar(); } }, p.autorizacion), "Cómo y cuándo autorizó (mínimo 15 caracteres)."),
      h("div", { class: "campo" }, h("span", {}, "Perfiles públicos (LinkedIn, Instagram, Facebook, X, TikTok)"), urls),
      h("div", { class: "fila" }, bLeer, h("span", { class: "espaciador" }),
        h("button", { class: "btn btn-sm btn-peligro-suave", onclick: async () => {
          if (await confirmar("¿Quitar a esta persona?", `${p.nombre || "Esta persona"} saldrá del archivo de autorizados al guardar. Sus hechos ya leídos no se borran.`, { boton: "Quitar", peligro: true })) {
            personas.splice(i, 1); marcar(); pintar();
          }
        } }, icono("trash"), "Quitar")));
  }

  function pintar() {
    zona.replaceChildren(...(personas.length ? personas.map(tarjeta) : [vacio("No hay personas autorizadas. Agrega la primera.", "idcard")]),
      h("button", { class: "btn", style: { alignSelf: "flex-start" }, onclick: () => {
        personas.push({ nombre: "", clave_cliente: "", autorizado: false, autorizacion: "", urls: [""] }); marcar(); pintar();
      } }, icono("plus"), "Agregar persona"));
  }

  async function cargar() {
    try {
      const r = await get("/api/perfiles/autorizados");
      personas = r.personas.map((p) => ({ ...p, nombre: p.nombre || "", clave_cliente: p.clave_cliente || "", autorizado: p.autorizado === true, autorizacion: p.autorizacion || "", urls: [...(p.urls || [])] }));
      sucio = false;
      pintarAvisos(r.avisos);
      pintar();
    } catch (e) {
      zona.replaceChildren(errorCaja(e, cargar));
    }
  }

  bGuardar.addEventListener("click", async () => {
    const r = await conBoton(bGuardar, () => put("/api/perfiles/autorizados", { personas }));
    if (r) { sucio = false; toast("Archivo de autorizados guardado."); pintarAvisos(r.avisos); }
  });
  bLeerTodos.addEventListener("click", () => leer(bLeerTodos, []));

  get("/api/tareas").then((ts) => ts.filter((t) => t.tipo === "ingesta_perfiles" && t.estado === "en_curso")
    .forEach((t) => zonaTareas.append(vigilarLogin(t.id), seguirTarea(t, { alTerminar: (res, z) => mostrarLectura(res, z) })))).catch(() => {});

  cargar();
  return h("div", { class: "pila" },
    alerta("Esta lista se llena sola cuando extraes URLs en Redes: el nombre sale del perfil. También puedes cargar personas a mano si ya las tienes. Hasta 50 perfiles por corrida.", "info"),
    zonaAvisos,
    h("div", { class: "barra-acciones" }, h("span", { class: "espaciador" }), bLeerTodos, bGuardar),
    zonaTareas, zona);
}
