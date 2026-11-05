"""Pruebas de las tareas web y del rol admin (sin BD ni Ollama).  Ejecutar:  python -m tests.test_tareas"""
import threading
import time

from app import governance, tareas


def _esperar(tarea, segundos=5):
    fin = time.time() + segundos
    while tarea.estado == "en_curso" and time.time() < fin:
        time.sleep(0.02)


def test_capturar_guarda_solo_lo_de_su_hilo():
    otro = threading.Thread(target=lambda: [print("(salida de otro hilo: debe verse en consola)") for _ in range(3)])
    with tareas.capturar() as registro:
        otro.start()
        print("línea 1")
        print("línea 2", end="")
        otro.join()
    assert registro.lineas == ["línea 1", "línea 2"]


def test_tarea_guarda_resultado_y_registro():
    def trabajo(t, n):
        t.avance(0, n)
        for i in range(n):
            print(f"paso {i}")
            t.avance(i + 1)
        return {"hecho": n}
    t = tareas.lanzar("prueba", "tarea de prueba", "ana", trabajo, 3)
    _esperar(t)
    assert t.estado == "terminada" and t.resultado == {"hecho": 3}
    assert t.lineas == ["paso 0", "paso 1", "paso 2"] and (t.actual, t.total) == (3, 3)
    assert t.vista(desde=2)["lineas"] == ["paso 2"]


def test_systemexit_de_un_comando_queda_como_error_legible():
    def comando(_t):
        print("intentando...")
        raise SystemExit("Indica ids, o usa --todos.")
    t = tareas.lanzar("prueba", "falla", "ana", comando)
    _esperar(t)
    assert t.estado == "error" and t.error == "Indica ids, o usa --todos."
    assert t.lineas[0] == "intentando..."


def test_cancelar_deja_de_correr():
    arranque = threading.Event()
    def trabajo(t):
        t.avance(0, 4)
        arranque.set()
        while not t.cancelada:
            time.sleep(0.02)
        return {"detenida": True}
    t = tareas.lanzar("prueba", "se cancela", "ana", trabajo)
    assert arranque.wait(2)
    tareas.marcar_cancelada(t)
    _esperar(t)
    assert t.estado == "cancelada" and t.resultado == {"detenida": True}


def test_admin_puede_todo_lo_del_asesor_y_ve_grupos_pequenos():
    assert governance.PERMISOS["asesor"] <= governance.PERMISOS["admin"]
    assert governance.autorizar("admin", "admin_conocimiento")
    assert not governance.autorizar("asesor", "admin_conocimiento")
    k = governance.K_MIN
    grupos = [("Medellín", k + 10), ("Pasto", k - 1)]          # independiente del K_MIN del .env
    assert governance.aplicar_k_anonimato(grupos, "admin") == grupos
    assert governance.aplicar_k_anonimato(grupos, "asesor") == grupos
    assert governance.aplicar_k_anonimato(grupos, "analista") == [("Medellín", k + 10)]


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
