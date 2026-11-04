// Panel: cifras generales de la base y trabajo pendiente según el rol.
import { get } from "../api.js";
import { kpi } from "../componentes.js";
import { irA, puede } from "../estado.js";
import { alerta, barras, cabecera, cargando, errorCaja, h, icono, num, pct, toast } from "../ui.js";

function valorBool(dist, buscado) {
  const f = (dist && dist.filas || []).find((x) => x.valor === buscado);
  return f ? f.n : 0;
}

function ordenarRangos(filas) {
  const n = (v) => { const m = String(v).match(/\d+/); return m ? Number(m[0]) : 999; };
  return [...filas].sort((a, b) => n(a.valor) - n(b.valor));
}

export async function render(cont) {
  const zona = h("div", { class: "pila" });
  const recargar = h("button", { class: "btn", onclick: () => cargar() }, icono("refresh"), "Actualizar");
  cont.append(cabecera("Panel", "Resumen de la base de clientes. Todas las cifras salen de SQL, nunca del modelo.", recargar), zona);

  async function cargar() {
    zona.replaceChildren(cargando());
    try {
      zona.replaceChildren(pintar(await get("/api/panel")));
    } catch (e) {
      zona.replaceChildren(errorCaja(e, cargar));
    }
  }
  cargar();
}

function pintar(d) {
  const dist = d.distribuciones;
  const correo = valorBool(dist.tiene_correo, "true");
  const celular = valorBool(dist.tiene_celular, "true");
  const kpis = [
    kpi("Clientes", num(d.total), { ico: "users" }),
    kpi("Con correo válido", num(correo), { ico: "mail", sub: `${pct(correo, d.total)} de la base` }),
    kpi("Con celular válido", num(celular), { ico: "whatsapp", sub: `${pct(celular, d.total)} de la base` }),
  ];
  if (d.mensajes) {
    const porRevisar = (d.mensajes.borrador || 0) + (d.mensajes.requiere_revision || 0);
    kpis.push(kpi("Borradores por revisar", num(porRevisar), {
      ico: "mail", href: "#/borradores", destacado: porRevisar > 0,
      sub: d.mensajes.requiere_revision ? `${num(d.mensajes.requiere_revision)} con alertas de validación` : "Listos para tu revisión",
    }));
    kpis.push(kpi("Aprobados sin enviar", num(d.mensajes.aprobado || 0), { ico: "check", href: "#/borradores", sub: `${num(d.mensajes.enviado || 0)} enviados en total` }));
  }
  if (d.pendientes_conocimiento != null) {
    kpis.push(kpi("Conocimiento por revisar", num(d.pendientes_conocimiento), { ico: "book", href: "#/conocimiento", destacado: d.pendientes_conocimiento > 0, sub: "Fragmentos del sitio sin aprobar" }));
  }
  if (d.pendientes_duplicados != null) {
    kpis.push(kpi("Posibles duplicados", num(d.pendientes_duplicados), { ico: "merge", href: "#/duplicados", destacado: d.pendientes_duplicados > 0, sub: "Pares de clientes por revisar" }));
  }
  if (d.pendientes_hechos != null) {
    kpis.push(kpi("Hechos de perfil por revisar", num(d.pendientes_hechos), { ico: "idcard", href: "#/perfiles", destacado: d.pendientes_hechos > 0, sub: "De perfiles públicos autorizados" }));
  }

  const alClic = (dim) => (f) => {
    if (f.valor === "sin_dato") { toast("No se puede filtrar por «Sin dato».", "info"); return; }
    irA("segmentos", { [dim]: f.valor });
  };
  const tarjeta = (titulo, dim, filas, max = 10) => h("div", { class: "card pila-sm" },
    h("div", { class: "card-cab", style: { marginBottom: "4px" } }, h("h2", {}, titulo),
      dist[dim].ocultos ? h("span", { class: "muted pequeño", title: `Grupos con menos de ${d.k_min} personas` }, `${dist[dim].ocultos} oculto(s)`) : null),
    filas.length ? barras(filas, { onClick: alClic(dim), max, total: d.total }) : h("span", { class: "muted" }, "Sin datos"));

  const ocultos = Object.values(dist).reduce((a, x) => a + x.ocultos, 0);
  return h("div", { class: "pila" },
    h("div", { class: "kpis" }, kpis),
    !puede("listar") && ocultos ? alerta(`Por privacidad, los grupos con menos de ${d.k_min} personas no se muestran a tu rol.`, "info") : null,
    h("div", { class: "grid-2" },
      tarjeta("Segmentos", "segmento", dist.segmento.filas),
      tarjeta("Producto de interés", "producto_interes", dist.producto_interes.filas),
      tarjeta("Rango de edad", "rango_edad", ordenarRangos(dist.rango_edad.filas), 12),
      tarjeta("Ciudades principales", "ciudad", dist.ciudad.filas),
      tarjeta("Género", "genero", dist.genero.filas)),
    h("p", { class: "muted pequeño" }, "Haz clic en una barra para explorar ese grupo en Segmentos."));
}
