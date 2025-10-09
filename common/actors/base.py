from abc import ABC, abstractmethod

class Actor(ABC):
    topic: str

    @abstractmethod
    def handle(self, msg: dict) -> dict:
        ...