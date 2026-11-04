// Estado compartido entre vistas (sesión, catálogos en caché y filtros que una vista le pasa a otra).
import { get } from "./api.js";

export const estado = {
  sesion: null,
  catalogo: null,
  opciones: null,
  presetFiltros: null,   // p. ej. un clic en una barra del panel abre Segmentos con ese filtro
};

export function puede(permiso) {
  return Boolean(estado.sesion && estado.sesion.permisos && estado.sesion.permisos.includes(permiso));
}

export async function catalogo() {
  if (!estado.catalogo) estado.catalogo = await get("/api/catalogo");
  return estado.catalogo;
}

export async function opciones(recargar = false) {
  if (!estado.opciones || recargar) estado.opciones = await get("/api/opciones");
  return estado.opciones;
}

export function tomarPreset() {
  const p = estado.presetFiltros;
  estado.presetFiltros = null;
  return p || {};
}

export function irA(vista, filtros) {
  if (filtros) estado.presetFiltros = filtros;
  const destino = `#/${vista}`;
  if (location.hash === destino) window.dispatchEvent(new HashChangeEvent("hashchange"));
  else location.hash = destino;
}
