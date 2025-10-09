from typing import Dict, Any
import zmq  
from common.actors.base import Actor

GA_ENDPOINT = "tcp://gestor_almacenamiento:5570"  


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
