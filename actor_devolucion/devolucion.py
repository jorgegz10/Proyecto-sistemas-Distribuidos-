from typing import Dict, Any
from common.actors.base import Actor

class Devolucion(Actor):
    topic = "devolucion"

    def handle(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        # 1) Registrar devolución
        # 2) Calcular multa si aplica (según diagrama de secuencia DevolucionLibro/FalloRecuperación)
        return {"ok": True, "accion": "registrar_devolucion"}

