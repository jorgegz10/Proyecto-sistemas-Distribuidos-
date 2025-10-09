from dataclasses import dataclass
from .tipos import TipoUsuario

@dataclass
class Usuario:
    id_usuario: str
    nombre: str
    tipo: TipoUsuario
    librosPrestados: int

    @classmethod
    def puedePrestar(cls, usuario: 'Usuario') -> bool:
        # Lógica para determinar si el usuario puede prestar más libros
        return usuario.librosPrestados < 5