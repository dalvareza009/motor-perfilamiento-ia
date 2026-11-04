"""Tareas en segundo plano para la web (lotes de mensajes, scraping) y captura de lo que imprimen.

Los comandos de ingesta informan con print(). En vez de reescribirlos, sys.stdout se reemplaza por un
proxy que, dentro de una tarea o de `capturar()`, guarda lo impreso por ESE hilo en su propio registro;
lo que imprimen los demás hilos sigue saliendo por la consola como siempre.
"""
import os
import sys
import threading
import time
import traceback
import uuid
from contextlib import contextmanager

MAX_LINEAS = 3000
MAX_TAREAS = 50


class _Salida:
    def __init__(self, original):
        self.original = original
        self.local = threading.local()

    def write(self, texto):
        destino = getattr(self.local, "registro", None)
        if destino is not None:
            destino.escribir(texto)
        else:
            self.original.write(texto)
        return len(texto)

    def flush(self):
        self.original.flush()

    def __getattr__(self, nombre):           # isatty, encoding, fileno... del stdout real
        return getattr(self.original, nombre)


for _flujo in (sys.stdout, sys.stderr):
    try:   # en Windows, con la salida redirigida (cp1252), un "✓" o "⚠" no debe tumbar el servidor
        _flujo.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
if not isinstance(sys.stdout, _Salida):
    sys.stdout = _Salida(sys.stdout)
_salida = sys.stdout


class Registro:
    def __init__(self):
        self.lineas = []
        self._pendiente = ""
        self._lock = threading.Lock()

    def escribir(self, texto):
        with self._lock:
            self._pendiente += texto
            *completas, self._pendiente = self._pendiente.split("\n")
            self.lineas.extend(completas)
            if len(self.lineas) > MAX_LINEAS:
                del self.lineas[: len(self.lineas) - MAX_LINEAS]

    def cerrar(self):
        if self._pendiente:
            self.escribir("\n")

    def texto(self):
        return "\n".join(self.lineas).strip()


@contextmanager
def capturar():
    """Guarda lo que se imprima en este hilo mientras dure el bloque."""
    registro, previo = Registro(), getattr(_salida.local, "registro", None)
    _salida.local.registro = registro
    try:
        yield registro
    finally:
        registro.cerrar()
        _salida.local.registro = previo


class Tarea(Registro):
    def __init__(self, tipo, descripcion, usuario):
        super().__init__()
        self.id = uuid.uuid4().hex[:12]
        self.tipo, self.descripcion, self.usuario = tipo, descripcion, usuario
        self.estado = "en_curso"
        self.resultado = self.error = None
        self.actual, self.total = 0, None
        self.inicio, self.fin = time.time(), None

    def avance(self, actual, total=None):
        self.actual = actual
        if total is not None:
            self.total = total

    def vista(self, desde=0):
        return {
            "id": self.id, "tipo": self.tipo, "descripcion": self.descripcion, "usuario": self.usuario,
            "estado": self.estado, "actual": self.actual, "total": self.total,
            "inicio": self.inicio, "fin": self.fin, "error": self.error, "resultado": self.resultado,
            "lineas": self.lineas[desde:], "n_lineas": len(self.lineas),
        }


TAREAS = {}
_lock = threading.Lock()


def lanzar(tipo, descripcion, usuario, fn, *args):
    """Corre fn(tarea, *args) en un hilo aparte. Lo que fn devuelve queda en tarea.resultado."""
    tarea = Tarea(tipo, descripcion, usuario)
    with _lock:
        TAREAS[tarea.id] = tarea
        for viejo in list(TAREAS)[:-MAX_TAREAS]:
            if TAREAS[viejo].estado != "en_curso":
                del TAREAS[viejo]

    def correr():
        _salida.local.registro = tarea
        try:
            tarea.resultado = fn(tarea, *args)
            tarea.estado = "terminada"
        except SystemExit as e:               # los comandos de ingesta avisan errores con SystemExit
            tarea.error, tarea.estado = str(e.code or "La tarea se detuvo."), "error"
        except Exception as e:
            tarea.error, tarea.estado = f"{type(e).__name__}: {e}", "error"
            tarea.escribir(traceback.format_exc())
        finally:
            tarea.cerrar()
            tarea.fin = time.time()
            _salida.local.registro = None

    sync = bool(os.getenv("VERCEL") or os.getenv("TAREAS_SYNC"))
    if sync:
        correr()
    else:
        threading.Thread(target=correr, name=f"tarea-{tarea.id}", daemon=True).start()
    return tarea


def obtener(id_tarea):
    return TAREAS.get(id_tarea)


def recientes(usuario=None, limite=15):
    lista = [t for t in TAREAS.values() if usuario is None or t.usuario == usuario]
    return sorted(lista, key=lambda t: t.inicio, reverse=True)[:limite]
