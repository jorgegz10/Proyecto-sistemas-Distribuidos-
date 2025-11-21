from .mensaje import Mensaje
from common.domain.tipos import TipoOperacion  # Make sure this import path is correct

from datetime import datetime

class Peticion(Mensaje):
    tipoOperacion: TipoOperacion
    isbn: str
    idUsuario: str
    fechaOperacion: datetime

    @classmethod
    def validar(cls, peticion: 'Peticion') -> bool: #modificar para hacerlo con bd
        if not peticion.isbn or not peticion.idUsuario:
            return False
        if peticion.tipoOperacion not in TipoOperacion:
            return False
        return True