from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any

from .mensaje import Mensaje


@dataclass
class Respuesta(Mensaje):
    exito: bool = False
    mensaje: str = ""
    fechaOperacion: str = field(default_factory=lambda: datetime.now().isoformat())
    datos: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        # Serializar campos principales de la respuesta
        return {
            "exito": self.exito,
            "mensaje": self.mensaje,
            "fechaOperacion": self.fechaOperacion,
            "datos": self.datos,
        }
