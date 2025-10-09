from enum import Enum

class TipoUsuario(Enum):
    ESTUDIANTE = "Estudiante"
    PROFESOR = "Profesor"

class EstadoPrestamo(Enum):
    ACTIVO = "Activo"
    RENOVADO = "Renovado"
    DEVUELTO = "Devuelto"
    VENCIDO = "Vencido"
class TipoOperacion(Enum):
    PRESTAR = "Prestamo"
    RENOVAR = "Renovacion"
    DEVOLVER = "Devolucion"
class estadoCircuit(Enum):
    CERRADO = "Cerrado"
    ABIERTO = "Abierto"
    MEDIO_ABIERTO = "Medio_Abierto"