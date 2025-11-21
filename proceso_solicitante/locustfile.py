from locust import User, task, between, events
import zmq
import json
from pathlib import Path
import time
import sys

# === Configuración inicial ===
ROOT = Path(__file__).resolve().parent
SOLICITUDES = ROOT / "solicitudes.txt"

# Leemos las líneas del archivo una sola vez
def cargar_renovaciones():
    renovaciones = []
    with SOLICITUDES.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 3 and parts[0].upper() == "RENO":
                renovaciones.append({"isbn": parts[1], "usuario": parts[2]})
    return renovaciones


# === Clase Locust ===
class RenovacionUser(User):
    wait_time = between(0.5, 2)  # intervalo entre solicitudes

    def on_start(self):
        """Se ejecuta al iniciar cada usuario Locust"""
        self.context = zmq.Context()
        self.renovaciones = cargar_renovaciones()
        self.indice = 0
        print(f"[LOCUST] Usuario iniciado. Renovaciones cargadas: {len(self.renovaciones)}", file=sys.stderr)

    @task
    def enviar_renovacion(self):
        """Envía una renovación y mide tiempo de respuesta"""
        # Crear nuevo socket para cada request (patrón ZMQ REQ/REP)
        socket_req = self.context.socket(zmq.REQ)
        socket_req.setsockopt(zmq.RCVTIMEO, 10000)  # timeout 10 segundos
        socket_req.setsockopt(zmq.SNDTIMEO, 10000)
        
        try:
            socket_req.connect("tcp://gestor_carga:5555")
            
            # Obtener datos rotando por el array
            data = self.renovaciones[self.indice % len(self.renovaciones)]
            self.indice += 1

            pet = {
                "operacion": "renovacion",
                "isbn": data["isbn"],
                "usuario": data["usuario"],
                "id": f"{data['isbn']}_{data['usuario']}_{time.time()}"
            }

            start_time = time.time()
            
            # Enviar petición
            socket_req.send_json(pet)
            
            # Recibir respuesta
            resp = socket_req.recv_json()
            total_time = (time.time() - start_time) * 1000  # ms

            # Reportar éxito a Locust
            events.request.fire(
                request_type="ZMQ",
                name="renovacion",
                response_time=total_time,
                response_length=len(json.dumps(resp)),
                exception=None,
            )
            
        except zmq.error.Again:
            total_time = (time.time() - start_time) * 1000
            print("[LOCUST] Timeout esperando respuesta", file=sys.stderr)
            events.request.fire(
                request_type="ZMQ",
                name="renovacion",
                response_time=total_time,
                response_length=0,
                exception=Exception("Timeout"),
            )
        except Exception as e:
            total_time = (time.time() - start_time) * 1000
            print(f"[LOCUST] Error: {e}", file=sys.stderr)
            events.request.fire(
                request_type="ZMQ",
                name="renovacion",
                response_time=total_time,
                response_length=0,
                exception=e,
            )
        finally:
            socket_req.close()

    def on_stop(self):
        """Cierra el contexto ZMQ"""
        self.context.term()
