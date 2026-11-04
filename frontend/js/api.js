// Cliente de la API: agrega el token de sesión y convierte los errores en mensajes legibles.
const CLAVE = "motor_sesion";

export const sesion = {
  get() {
    try { return JSON.parse(sessionStorage.getItem(CLAVE)) || null; } catch { return null; }
  },
  set(datos) {
    try { sessionStorage.setItem(CLAVE, JSON.stringify(datos)); } catch { /* modo privado */ }
  },
  limpiar() {
    try { sessionStorage.removeItem(CLAVE); } catch { /* modo privado */ }
  },
};

export async function api(ruta, { metodo = "GET", datos } = {}) {
  const s = sesion.get();
  const opciones = { method: metodo, headers: {} };
  if (s?.token) opciones.headers.Authorization = `Bearer ${s.token}`;
  if (datos !== undefined) {
    opciones.headers["Content-Type"] = "application/json";
    opciones.body = JSON.stringify(datos);
  }
  let r;
  try {
    r = await fetch(ruta, opciones);
  } catch {
    throw new Error("No hay conexión con el servidor. ¿Sigue corriendo  python -m app.api ?");
  }
  const texto = await r.text();
  let cuerpo = null;
  try { cuerpo = texto ? JSON.parse(texto) : null; } catch { cuerpo = texto; }
  if (r.status === 401 && s) {
    sesion.limpiar();
    window.dispatchEvent(new Event("sesion-vencida"));
  }
  if (!r.ok) {
    let msg = cuerpo && cuerpo.detail;
    if (Array.isArray(msg)) msg = msg.map((e) => `${(e.loc || []).slice(1).join(".")}: ${e.msg}`).join("; ");
    throw new Error(msg || `Error ${r.status}`);
  }
  return cuerpo;
}

export const get = (ruta) => api(ruta);
export const post = (ruta, datos = {}) => api(ruta, { metodo: "POST", datos });
export const put = (ruta, datos = {}) => api(ruta, { metodo: "PUT", datos });
export const del = (ruta) => api(ruta, { metodo: "DELETE" });
