from dataclasses import dataclass, field
from datetime import datetime
import uuid

@dataclass
class Mensaje:
    topico: str
    contenido: str
    date: datetime = field(default_factory=datetime.now)
    headers: dict[str, str] = field(default_factory=dict)
