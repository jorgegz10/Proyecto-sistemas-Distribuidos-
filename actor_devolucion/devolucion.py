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
    print(f"[ActorDevolucion] Conectando a {gestor_pub_addr}")
    socket_sub.connect(gestor_pub_addr)
    
    # Suscribirse al tópico "devolucion"
    socket_sub.setsockopt_string(zmq.SUBSCRIBE, "devolucion")
    print("[ActorDevolucion] Suscrito al tópico 'devolucion'")
    
    # Crear instancia del actor
    actor = Devolucion()
    print("[ActorDevolucion] Listo para procesar devoluciones")
    
    # Bucle principal
    while True:
        try:
            # Recibir mensaje (formato: "topico {json}")
            raw_msg = socket_sub.recv_string()
            parts = raw_msg.split(" ", 1)
            
            if len(parts) == 2:
                _, data_str = parts
                msg = json.loads(data_str)
                
                print(f"[ActorDevolucion] Mensaje recibido: {msg}")
                result = actor.handle(msg)
                print(f"[ActorDevolucion] Resultado: {result}")
            
        except KeyboardInterrupt:
            print("\n[ActorDevolucion] Deteniendo...")
            break
        except Exception as e:
            print(f"[ActorDevolucion] Error: {e}")
    
    # Limpieza
    socket_sub.close()
    context.term()
    print("[ActorDevolucion] Terminado")


if __name__ == "__main__":
    main()
