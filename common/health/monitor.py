import time
import threading
import zmq
from typing import Callable, Dict

class HealthMonitor:
    """
    Hace ping (REQ) a endpoints REP de health. Notifica cambios (UP/DOWN) por callback.
    """
    def __init__(self, poll_interval: float = 2.0, timeout_ms: int = 700):
        self.poll_interval = poll_interval
        self.timeout_ms = timeout_ms
        self.targets: Dict[str, str] = {}         # name -> endpoint
        self.status: Dict[str, str] = {}          # name -> "UP"/"DOWN"
        self._on_change: Callable[[str, str], None] = lambda n, s: None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def add_target(self, name: str, endpoint: str):
        self.targets[name] = endpoint
        self.status.setdefault(name, "UNKNOWN")

    def on_change(self, cb: Callable[[str, str], None]):
        self._on_change = cb

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=1.0)

    def _probe(self, ctx: zmq.Context, endpoint: str) -> bool:
        s = ctx.socket(zmq.REQ)
        s.rcvtimeo = self.timeout_ms
        s.sndtimeo = self.timeout_ms
        s.linger = 0
        s.connect(endpoint)
        try:
            s.send_json({"ping": True})
            _ = s.recv_json()
            return True
        except Exception:
            return False
        finally:
            s.close()

    def _loop(self):
        ctx = zmq.Context.instance()
        while not self._stop.is_set():
            for name, ep in self.targets.items():
                ok = self._probe(ctx, ep)
                new_state = "UP" if ok else "DOWN"
                if self.status.get(name) != new_state:
                    self.status[name] = new_state
                    self._on_change(name, new_state)
            time.sleep(self.poll_interval)
