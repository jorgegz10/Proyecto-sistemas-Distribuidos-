from dataclasses import dataclass, field
from datetime import datetime
from .usuario import Usuario
from .libro import Libro
from .tipos import EstadoPrestamo

@dataclass
class Prestamo:
    id_prestamo: str
    isbn: str
    usuarioid: str
    renovacionesUsadas: int
    estado: EstadoPrestamo #se saca de la bd
    fechaPrestamo: datetime = field(default_factory=datetime.now)
    fechaDevolucion: datetime = field(default_factory=lambda: datetime.now().replace(hour=23, minute=59)) #modificar dependindo del tiempo de prestamo

    def renovar(self) -> bool:
        pass

    def devolver(self) -> None:
        if self.estado not in (EstadoPrestamo.ACTIVO, EstadoPrestamo.RENOVADO):
            return False
        self.estado = EstadoPrestamo.DEVUELTO
        self.libro.disponible = True

    def puedeRenovar(self) -> bool:
        return self.estado == EstadoPrestamo.ACTIVO
