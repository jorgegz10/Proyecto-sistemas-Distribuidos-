from typing import Dict, Any
import os
import zmq  
from common.actors.base import Actor

# Allow overriding the gestor_almacenamiento endpoint via env vars so this
# actor can run on a different machine than the storage manager.
GA_ENDPOINT = os.getenv("GESTOR_ALMACENAMIENTO_ADDR") or os.getenv("GESTOR_ALMACENAMIENTO") or "tcp://gestor_almacenamiento:5570"


class Devolucion(Actor):
    topic = "devolucion"

    def __init__(self, *args, **kwargs):  
        super().__init__(*args, **kwargs)
        self._ctx = zmq.Context.instance()
        self._req = self._ctx.socket(zmq.REQ)
        self._req.RCVTIMEO = 5000  # ms
        self._req.SNDTIMEO = 5000
        self._req.connect(GA_ENDPOINT)

    def handle(self, msg: Dict[str, Any]) -> Dict[str, Any]:  #
        # Mensaje publicado por el GC en el tópico 'devolucion'
        isbn = msg.get("isbn") or (msg.get("data") or {}).get("isbn")
        usuario = msg.get("usuario") or (msg.get("data") or {}).get("usuario")
        if not isbn or not usuario:
            return {"ok": False, "accion": "registrar_devolucion", "error": "faltan_campos"}

        # Llamada síncrona al GA (transacción del diagrama)
        peticion = {"accion": "aplicar_devolucion", "isbn": isbn, "usuario": usuario}
        try:
            self._req.send_json(peticion)
            resp = self._req.recv_json()
        except Exception as e:
            return {"ok": False, "accion": "error_devolucion", "error": str(e)}

        if isinstance(resp, dict) and resp.get("status") == "ok":
            return {"ok": True, "accion": "devolucionCompletada", "detalle": resp.get("detalle", "")}
        else:
            return {"ok": False, "accion": "error_devolucion", "detalle": resp}

    def __del__(self):  # <<< CAMBIO
        try:
            self._req.close(0)
        except Exception:
            pass


def main():
    """Punto de entrada principal del actor de devolución"""
    import json
    
    print("[ActorDevolucion] Iniciando...")
    
    # Configurar conexión al gestor de carga (PUB/SUB)
    context = zmq.Context()
    socket_sub = context.socket(zmq.SUB)
    
    # Conectar al publisher del gestor de carga
    gestor_pub_addr = os.getenv("GESTOR_CARGA_PUB_ADDR", "tcp://gestor_carga:5556")
    socket_sub.connect(gestor_pub_addr)
    socket_sub.setsockopt_string(zmq.SUBSCRIBE, "devolucion")
    
    # REP socket para peticiones síncronas del gestor
    socket_rep = context.socket(zmq.REP)
    socket_rep.bind("tcp://*:5562")
    
    poller = zmq.Poller()
    poller.register(socket_sub, zmq.POLLIN)
    poller.register(socket_rep, zmq.POLLIN)
    
    print(f"[ActorDevolucion] PUB/SUB conectado a {gestor_pub_addr}, REP escuchando en 5562")
    
    # Crear instancia del actor
    actor = Devolucion()
    
    # Bucle principal
    while True:
        try:
            events = dict(poller.poll())
            
            if socket_sub in events:
                # Recibir mensaje PUB/SUB (formato: "topico {json}")
                raw_msg = socket_sub.recv_string()
                parts = raw_msg.split(" ", 1)
                
                if len(parts) == 2:
                    _, data_str = parts
                    msg = json.loads(data_str)
                    result = actor.handle(msg)
                    print(f"[ActorDevolucion] Evento resultado: {result}")
            
            if socket_rep in events:
                # Recibir petición REQ/REP
                try:
                    req = socket_rep.recv_json()
                    result = actor.handle(req)
                    # Normalizar respuesta para gestor_carga
                    response = {
                        "exito": result.get("ok", False),
                        "devolucion": result.get("detalle", ""),
                        "error": result.get("error")
                    }
                    socket_rep.send_json(response)
                    print(f"[ActorDevolucion] Req/Rep resultado: {response}")
                except Exception as e:
                    socket_rep.send_json({"exito": False, "error": str(e)})
            
        except KeyboardInterrupt:
            print("\n[ActorDevolucion] Deteniendo...")
            break
        except Exception as e:
            print(f"[ActorDevolucion] Error: {e}")
    
    # Limpieza
    socket_sub.close()
    socket_rep.close()
    context.term()
    print("[ActorDevolucion] Terminado")


if __name__ == "__main__":
    main()
