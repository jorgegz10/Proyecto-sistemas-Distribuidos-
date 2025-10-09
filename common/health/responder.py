import threading
import zmq

class HealthResponder:
    """
    REP simple para health-check. Responde {"status":"ok"} a cualquier petición.
    Ejecutar en un thread del proceso (GC, Actor, GA).
    """
    def __init__(self, bind_endpoint: str):
        self.bind_endpoint = bind_endpoint
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=1.0)

    def _serve(self):
        ctx = zmq.Context.instance()
        sock = ctx.socket(zmq.REP)
        sock.linger = 0
        sock.bind(self.bind_endpoint)
        while not self._stop.is_set():
            try:
                msg = sock.recv_json(flags=zmq.NOBLOCK)
                # Podrías incluir métricas aquí: carga, colas, etc.
                sock.send_json({"status": "ok"})
            except zmq.Again:
                pass
