import os
import zmq
import json
from typing import Dict, Any
from common.actors.base import Actor


class ActorRenovacion(Actor):
    topic = "renovacion"

    def __init__(self):
        super().__init__()
        # Crear socket REQ para comunicarse con gestor_almacenamiento
        self.context = zmq.Context()
        self.storage_socket = self.context.socket(zmq.REQ)
        self.storage_socket.RCVTIMEO = 5000
        self.storage_socket.SNDTIMEO = 5000
        
        storage_host = os.getenv("GESTOR_ALMACENAMIENTO_HOST", "gestor_almacenamiento")
        storage_port = os.getenv("GESTOR_ALMACENAMIENTO_PORT", "5570")
        storage_addr = f"tcp://{storage_host}:{storage_port}"
        
        print(f"[ActorRenovacion] Conectando a gestor_almacenamiento en {storage_addr}")
        self.storage_socket.connect(storage_addr)

    def handle(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        print(f"[ActorRenovacion] Procesando mensaje: {msg}")
        
        # Extraer datos del mensaje - puede venir directo o en payload
        isbn = msg.get("isbn") or msg.get("payload", {}).get("isbn")
        usuario = msg.get("usuario") or msg.get("payload", {}).get("usuario")
        
        if not isbn or not usuario:
            print(f"[ActorRenovacion] Datos inválidos: isbn={isbn}, usuario={usuario}")
            return {"ok": False, "accion": "datos_invalidos"}

        try:
            # Enviar solicitud de renovación al gestor de almacenamiento
            print(f"[ActorRenovacion] Solicitando renovación para isbn={isbn}, usuario={usuario}")
            request = {
                "action": "actualizar_renovacion",
                "isbn": isbn,
                "usuario": usuario
            }
            self.storage_socket.send_json(request)
            
            # Esperar respuesta
            response = self.storage_socket.recv_json()
            print(f"[ActorRenovacion] Respuesta del gestor: {response}")
            
            if response.get("status") == "ok":
                return {
                    "ok": True,
                    "accion": "renovacionCompletada",
                    "detalle": response.get("detalle", "Renovación completada"),
                    "datos": response.get("datos", {})
                }
            else:
                return {
                    "ok": False,
                    "accion": "renovacionRechazada",
                    "error": response.get("error", "Error desconocido")
                }
                
        except zmq.Again:
            print("[ActorRenovacion] Timeout al comunicarse con gestor_almacenamiento")
            return {"ok": False, "accion": "timeout", "error": "Timeout al procesar renovación"}
        except Exception as e:
            print(f"[ActorRenovacion] Error: {e}")
            return {"ok": False, "accion": "error", "error": str(e)}


def main():
    context = zmq.Context()

    # SUB socket para eventos pub/sub
    socket_sub = context.socket(zmq.SUB)
    gc_pub_addr = os.getenv("GESTOR_CARGA_PUB_ADDR", "tcp://gestor_carga:5556")
    socket_sub.connect(gc_pub_addr)
    socket_sub.setsockopt_string(zmq.SUBSCRIBE, ActorRenovacion.topic)

    # REP socket para peticiones síncronas del gestor
    socket_rep = context.socket(zmq.REP)
    socket_rep.bind("tcp://*:5561")

    poller = zmq.Poller()
    poller.register(socket_sub, zmq.POLLIN)
    poller.register(socket_rep, zmq.POLLIN)

    print(f"[ActorRenovacion] PUB/SUB conectado a {gc_pub_addr}, REP escuchando en 5561")

    actor = ActorRenovacion()

    try:
        while True:
            events = dict(poller.poll())
            
            if socket_sub in events:
                try:
                    raw = socket_sub.recv_string()
                    topic, data = raw.split(" ", 1)
                    msg = json.loads(data)
                    result = actor.handle(msg)
                    print(f"[ActorRenovacion] Evento resultado: {result}")
                except Exception as e:
                    print(f"[ActorRenovacion] Error en PUB/SUB: {e}")
            
            if socket_rep in events:
                try:
                    req = socket_rep.recv_json()
                    result = actor.handle(req)
                    # Normalizar respuesta para gestor_carga
                    response = {
                        "exito": result.get("ok", False),
                        "renovacion": result.get("datos", {}),
                        "error": result.get("error")
                    }
                    socket_rep.send_json(response)
                    print(f"[ActorRenovacion] Req/Rep resultado: {response}")
                except Exception as e:
                    socket_rep.send_json({"exito": False, "error": str(e)})
    except KeyboardInterrupt:
        print("[ActorRenovacion] Interrumpido")
    finally:
        socket_sub.close()
        socket_rep.close()
        context.term()


if __name__ == "__main__":
    main()
