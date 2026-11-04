// Duplicados: un perfil por persona. Pares candidatos lado a lado, con el puntaje explicado campo por campo.
import { get, post } from "../api.js";
import { abrirCliente } from "../componentes.js";
import {
  alerta, badge, cabecera, cargando, conBoton, confirmar, errorCaja, fecha, h, icono, num, pestañas, poner, toast,
  vacio,
} from "../ui.js";

let estadoActivo = "pendiente";

const CAMPOS = [
  ["Nombre", "nombre"], ["Género", "genero"], ["Edad", "edad"], ["Correo", "correo"], ["Celular", "celular"],
  ["Ciudad", "ciudad"], ["Profesión", "profesion"], ["Universidad", "universidad"],
  ["Producto de interés", "producto_interes"], ["Medio de origen", "medio"], ["Registrado", "fecha_registro"],
];

const normal = (v) => String(v ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

function aporte(d) {
  return h("span", { class: `aporte ${d.aporte >= 0 ? "suma" : "resta"}`, title: d.campo }, `${d.aporte > 0 ? "+" : ""}${d.aporte} ${d.motivo}`);
}

function medidor(puntaje, auto, revision) {
  const tope = Math.max(auto * 2, puntaje);
  const pctDe = (x) => `${Math.max(0, Math.min(100, (100 * x) / tope))}%`;
  const color = puntaje >= auto ? "var(--ok)" : puntaje >= revision ? "var(--warn)" : "var(--muted)";
  return h("div", { class: "medidor", title: `Se une solo desde ${auto}; revisión desde ${revision}` },
    h("strong", { style: { color } }, num(puntaje)),
    h("span", { class: "barra-pista" },
      h("span", { class: "barra-relleno", style: { width: pctDe(puntaje), background: color } }),
      h("span", { class: "umbral", style: { left: pctDe(revision) } }),
      h("span", { class: "umbral", style: { left: pctDe(auto) } })));
}

function tarjetaPar(p, ctx, alCambiar) {
  const a = p.a || {};
  const b = p.b || {};
  const celda = (campo, valor, otro) => {
    const texto = campo === "fecha_registro" ? (valor ? fecha(valor).split(",")[0] : null) : valor;
    if (texto == null || texto === "") return h("td", { class: "falta" }, "—");
    const clase = otro == null || otro === "" ? "" : normal(valor) === normal(otro) ? "igual" : "difiere";
    return h("td", { class: clase }, String(texto));
  };
  const cabeza = (r, id, clave) => h("th", {},
    h("div", {}, `Registro #${id}`),
    clave ? h("button", { class: "btn btn-fantasma btn-sm", style: { padding: "0 4px" }, title: "Abrir ficha del cliente", onclick: () => abrirCliente(clave) }, h("span", { class: "mono" }, clave)) : null);

  const acciones = h("div", { class: "fila" });
  const boton = (texto, clase, ico, accion) => {
    const btn = h("button", { class: `btn btn-sm ${clase}` }, icono(ico), texto);
    btn.addEventListener("click", () => accion(btn));
    return btn;
  };
  const unir = boton(p.estado === "distinto" ? "Unir de todas formas" : "Unir: es la misma persona", "btn-primario", "merge", async (btn) => {
    const r = await conBoton(btn, () => post(`/api/duplicados/${p.id_par}/unir`));
    if (!r) return;
    toast(`Unidos en ${r.clave_cliente}.`);
    (r.avisos || []).forEach((x) => toast(x, "info", 7000));
    alCambiar();
  });
  const distintos = boton(p.estado === "unido" ? "No son la misma persona: separar" : "Son personas distintas",
    "btn-peligro-suave", p.estado === "unido" ? "split" : "x", async (btn) => {
      if (p.estado === "unido" && !(await confirmar("¿Separar estos registros?",
        `El registro #${p.id_registro_b} saldrá del cliente ${p.clave_b} y quedará como cliente aparte. Sus borradores y perfil IA se quedan en ${p.clave_a}.`,
        { boton: "Separar", peligro: true }))) return;
      const r = await conBoton(btn, () => post(`/api/duplicados/${p.id_par}/distintos`));
      if (!r) return;
      toast(r.separado ? `Registro #${r.separado} separado como ${r.clave_cliente}.` : "Marcados como personas distintas: no se volverán a proponer.");
      alCambiar();
    });
  if (p.estado === "pendiente") acciones.append(distintos, unir);
  else if (p.estado === "unido") acciones.append(distintos);
  else acciones.append(unir);

  const decision = p.estado === "pendiente" ? badge("Por revisar", "warn")
    : p.estado === "unido" ? badge(p.decidido_por === "automatico" ? "Unido automáticamente" : `Unido por ${p.decidido_por}`, "ok")
      : badge(`Distintos · ${p.decidido_por}`, "");

  return h("article", { class: "card pila-sm" },
    h("div", { class: "fila" },
      h("strong", { style: { flex: "1", minWidth: "200px" } }, `${a.nombre || "—"}  ·  ${b.nombre || "—"}`),
      decision, medidor(Number(p.puntaje), ctx.auto, ctx.revision)),
    h("div", { class: "fila", style: { gap: "4px" } }, (p.detalle || []).map(aporte)),
    h("div", { class: "tabla-envoltura" }, h("table", { class: "comparacion" },
      h("thead", {}, h("tr", {}, h("th", {}, "Campo"), cabeza(a, p.id_registro_a, p.clave_a), cabeza(b, p.id_registro_b, p.clave_b))),
      h("tbody", {}, CAMPOS.map(([titulo, campo]) => h("tr", {}, h("td", {}, titulo), celda(campo, a[campo], b[campo]), celda(campo, b[campo], a[campo])))))),
    h("div", { class: "fila" },
      h("span", { class: "muted pequeño", style: { flex: "1" } },
        p.fecha_decision ? `Decidido ${fecha(p.fecha_decision)}` : `Detectado ${fecha(p.creado)}`),
      acciones));
}

function reporte(r) {
  const partes = [h("div", {}, h("strong", {}, `${num(r.registros)} registros → ${num(r.clientes)} clientes únicos.`),
    ` Se compararon ${num(r.pares_evaluados)} pares candidatos.`)];
  if (r.fusiones.length) {
    partes.push(h("div", {}, `Unidos automáticamente (${r.fusiones.length}):`),
      h("ul", {}, r.fusiones.map((f) => h("li", {}, `#${f.registros[0]} ${f.nombres[0]} + #${f.registros[1]} ${f.nombres[1]} (puntaje ${f.puntaje})`))));
  }
  partes.push(h("div", {}, r.pendientes.length ? `${r.pendientes.length} par(es) quedaron para tu revisión.` : "No hay pares nuevos para revisar."));
  (r.avisos || []).forEach((x) => partes.push(h("div", { class: "muted" }, `⚠ ${x}`)));
  (r.bloques_omitidos || []).forEach(([k, n]) => partes.push(h("div", { class: "muted" }, `⚠ Bloque muy grande omitido (${n} registros): ${k}`)));
  return alerta(partes, r.pendientes.length ? "warn" : "ok");
}

export async function render(cont) {
  const zonaReporte = h("div");
  const lista = h("div", { class: "pila" }, cargando());
  const definicion = [{ id: "pendiente", texto: "Por revisar" }, { id: "unido", texto: "Unidos" }, { id: "distinto", texto: "Personas distintas" }];
  const tabs = pestañas(definicion, estadoActivo, (id) => { estadoActivo = id; cargar(); });
  const ctx = { auto: 12, revision: 6 };

  async function cargar() {
    lista.replaceChildren(cargando());
    try {
      const r = await get(`/api/duplicados?estado=${estadoActivo}`);
      if (!r.instalado) {
        lista.replaceChildren(alerta(["La deduplicación aún no está instalada en la base. Ejecuta una vez: ",
          h("code", {}, "python -m app.deduplicacion migrar --simular"), " para revisar y luego ",
          h("code", {}, "python -m app.deduplicacion migrar"), "."], "warn"));
        return;
      }
      ctx.auto = r.umbral_auto;
      ctx.revision = r.umbral_revision;
      tabs.actualizar(definicion.map((d) => ({ ...d, n: r.conteo[d.id] || 0 })));
      poner(lista, r.pares.length
        ? r.pares.map((p) => tarjetaPar(p, ctx, cargar))
        : vacio(estadoActivo === "pendiente" ? "No hay posibles duplicados por revisar." : "No hay pares en este estado.", "check"));
    } catch (e) {
      lista.replaceChildren(errorCaja(e, cargar));
    }
  }

  const bBuscar = h("button", { class: "btn btn-primario" }, icono("refresh"), "Buscar duplicados ahora");
  bBuscar.addEventListener("click", async () => {
    const r = await conBoton(bBuscar, () => post("/api/duplicados/sincronizar"));
    if (!r) return;
    zonaReporte.replaceChildren(reporte(r));
    cargar();
  });

  cont.append(
    cabecera("Duplicados de clientes", "Cada persona debe tener un solo perfil: es el que usa el modelo para recomendar y redactar.", bBuscar),
    h("details", { class: "card" }, h("summary", {}, "¿Cómo decide si dos registros son la misma persona?"),
      h("div", { class: "pila-sm", style: { marginTop: "10px" } },
        h("p", {}, "Compara campo por campo, sin tildes ni mayúsculas. Lo que coincide suma y lo que se contradice resta:"),
        h("div", { class: "fila", style: { gap: "4px" } },
          [["+10", "mismo correo"], ["+8", "mismo celular"], ["+5", "mismo nombre"], ["+2", "misma edad"], ["+1", "edad ±1"],
            ["+1", "misma ciudad"], ["+1", "profesión o universidad compatibles"]].map(([n, t]) => h("span", { class: "aporte suma" }, `${n} ${t}`)),
          [["−5", "nombres distintos"], ["−5", "género distinto"], ["−4", "edades muy distintas"], ["−2", "correos o celulares distintos"]]
            .map(([n, t]) => h("span", { class: "aporte resta" }, `${n} ${t}`))),
        h("p", { class: "muted" }, "Desde 12 puntos se unen solos; entre 6 y 11 quedan aquí para tu revisión; por debajo se consideran personas distintas. Una familia que comparte celular no se une: los nombres y el género restan."),
        h("p", { class: "muted" }, "El perfil unido toma de cada campo el dato más reciente (el nombre, la versión mejor escrita) y conserva todos los correos y celulares. Las decisiones de «personas distintas» se recuerdan."))),
    zonaReporte,
    h("div", { class: "card pila" }, tabs.el, lista));
  cargar();
}
