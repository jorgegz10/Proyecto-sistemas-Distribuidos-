import zmq
import json
import os
from common.actors.base import Actor


class ActorPrestamo(Actor):
    topic = "prestamo"

    def __init__(self):
        super().__init__()
        # Conectar al gestor de almacenamiento
        self.context_almacenamiento = zmq.Context()
        self.socket_almacenamiento = self.context_almacenamiento.socket(zmq.REQ)
        
        # Permitir múltiples hosts para failover
        gestor_almacenamiento_hosts = os.getenv(
            "GESTOR_ALMACENAMIENTO", 
            "gestor_almacenamiento:5570"
        ).split(",")
        
        for host in gestor_almacenamiento_hosts:
            addr = f"tcp://{host.strip()}"
            print(f"[ActorPrestamo] Conectando a almacenamiento: {addr}")
            self.socket_almacenamiento.connect(addr)
        
        self.socket_almacenamiento.setsockopt(zmq.RCVTIMEO, 5000)
        self.socket_almacenamiento.setsockopt(zmq.SNDTIMEO, 5000)

    def handle(self, msg: dict) -> dict:
        """Procesa un préstamo de libro"""
        print(f"[ActorPrestamo] Procesando: {msg}")
        
        try:
            # Extraer datos del mensaje
            isbn = msg.get("isbn")
            usuario = msg.get("usuario")
            
            if not isbn or not usuario:
                print(f"[ActorPrestamo] Datos incompletos: isbn={isbn}, usuario={usuario}")
                return {"ok": False, "error": "Datos incompletos"}
            
            # Solicitar procesamiento al gestor de almacenamiento
            peticion = {
                "accion": "procesar_prestamo",
                "isbn": isbn,
                "usuario": usuario
            }
            
            print(f"[ActorPrestamo] Enviando petición al almacenamiento: {peticion}")
            self.socket_almacenamiento.send_json(peticion)
            
            # Esperar respuesta
            respuesta = self.socket_almacenamiento.recv_json()
            print(f"[ActorPrestamo] Respuesta del almacenamiento: {respuesta}")
            
            # Procesar respuesta
            if respuesta.get("status") == "ok":
                return {
                    "ok": True,
                    "accion": "prestamo_registrado",
                    "datos": respuesta.get("datos", {})
                }
            else:
                return {
                    "ok": False,
                    "error": respuesta.get("error", "Error desconocido"),
                    "detalle": respuesta.get("detalle", "")
                }
                
        except zmq.error.Again:
            print("[ActorPrestamo] Timeout al comunicarse con almacenamiento")
            return {"ok": False, "error": "Timeout al comunicarse con almacenamiento"}
        except Exception as e:
            print(f"[ActorPrestamo] Error al procesar préstamo: {e}")
            return {"ok": False, "error": str(e)}
    
    def __del__(self):
        """Limpieza de recursos"""
        try:
            self.socket_almacenamiento.close()
            self.context_almacenamiento.term()
        except Exception:
            pass


def main():
    context = zmq.Context()

    # SUB socket para eventos pub/sub
    socket_sub = context.socket(zmq.SUB)
    socket_sub.connect("tcp://gestor_carga:5556")
    socket_sub.setsockopt_string(zmq.SUBSCRIBE, ActorPrestamo.topic)

    # REP socket para peticiones síncronas de gestor
    socket_rep = context.socket(zmq.REP)
    socket_rep.bind("tcp://*:5560")

    poller = zmq.Poller()
    poller.register(socket_sub, zmq.POLLIN)
    poller.register(socket_rep, zmq.POLLIN)

    print("[ActorPrestamo] Esperando mensajes... (PUB/SUB y REP en 5560)")

    actor = ActorPrestamo()

    while True:
        events = dict(poller.poll())
        if socket_sub in events:
            raw = socket_sub.recv_string()
            topic, data = raw.split(" ", 1)
            msg = json.loads(data)
            result = actor.handle(msg)
            print(f"[ActorPrestamo] Evento resultado: {result}")

        if socket_rep in events:
            try:
                req = socket_rep.recv_json()
                result = actor.handle(req)
                socket_rep.send_json(result)
                print(f"[ActorPrestamo] Req/Rep resultado: {result}")
            except Exception as e:
                socket_rep.send_json({"ok": False, "error": str(e)})


if __name__ == "__main__":
    main()
