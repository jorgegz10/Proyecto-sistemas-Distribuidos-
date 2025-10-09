from dataclasses import dataclass

@dataclass
class Libro:
    id_libro: str
    isbn: str
    titulo: str
    autor: str
    ejemplares: int
    ejemplaresTotales: int

    @classmethod
    def disponible(self) -> bool:
        return self.ejemplares > 0 #consultar en bd si hay ejemplres
    
    @classmethod
    def actualizar_disponibilidad(cls, id_libro: str, disponible: bool):
        # Aquí se actualizaría la disponibilidad en la base de datos
        pass