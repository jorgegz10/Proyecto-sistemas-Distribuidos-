from locust import User, task, between, events
import zmq
import json
from pathlib import Path
import time


# === Configuración inicial ===
ROOT = Path(__file__).resolve().parent
DEVOLUCIONES = ROOT / "devoluciones.txt"

# Leemos las líneas del archivo una sola vez
def cargar_devoluciones():
    with DEVOLUCIONES.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 3 and parts[0].upper() == "DEVO":
                yield {"isbn": parts[1], "usuario": parts[2]}


# === Clase Locust ===
class DevolucionUser(User):
    wait_time = between(0.5, 2)  # intervalo entre solicitudes

    def on_start(self):
        """Se ejecuta al iniciar cada usuario Locust"""
        context = zmq.Context()
        self.socket_req = context.socket(zmq.REQ)
        # Cambia IP o hostname según tu red o docker-compose
        self.socket_req.setsockopt(zmq.RCVTIMEO, 2000) # 2 seconds timeout
        self.socket_req.connect("tcp://gestor_carga:5555")
        self.data_iter = iter(cargar_devoluciones())

    @task
    def enviar_devolucion(self):
        """Envía una devolución y mide tiempo de respuesta"""
        try:
            data = next(self.data_iter)
        except StopIteration:
            self.data_iter = iter(cargar_devoluciones())
            data = next(self.data_iter)

        pet = {
            "operacion": "devolucion",
            "isbn": data["isbn"],
            "usuario": data["usuario"],
            "id": f"{data['isbn']}_{data['usuario']}"
        }

        start_time = time.time()
        try:
            self.socket_req.send_json(pet)
            resp = self.socket_req.recv_json()
            total_time = (time.time() - start_time) * 1000  # ms

            # Reportar éxito a Locust
            events.request.fire(
                request_type="ZMQ",
                name="devolucion",
                response_time=total_time,
                response_length=len(json.dumps(resp)),
                exception=None,
            )
        except zmq.Again:
            total_time = (time.time() - start_time) * 1000
            events.request.fire(
                request_type="ZMQ",
                name="devolucion",
                response_time=total_time,
                response_length=0,
                exception=Exception("ZMQ Timeout"),
            )
            # Recreate socket on timeout to clear state
            self.socket_req.close()
            context = zmq.Context()
            self.socket_req = context.socket(zmq.REQ)
            self.socket_req.setsockopt(zmq.RCVTIMEO, 2000)
            self.socket_req.connect("tcp://gestor_carga:5555")

        except Exception as e:
            total_time = (time.time() - start_time) * 1000
            events.request.fire(
                request_type="ZMQ",
                name="devolucion",
                response_time=total_time,
                response_length=0,
                exception=e,
            )

    def on_stop(self):
        """Cierra el socket"""
        self.socket_req.close()
