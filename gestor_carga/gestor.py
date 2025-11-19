import zmq
import json
from typing import Dict, Any
from types import SimpleNamespace
from datetime import datetime, timedelta

from common.messaging.respuesta import Respuesta
from common.resilience.circuitBreaker import CircuitBreaker


class ZMQPublisher:
    def __init__(self, context: zmq.Context, endpoint: str):
        self.socket = context.socket(zmq.PUB)
        self.socket.bind(endpoint)

    def publish(self, topic: str, message: str) -> None:
        self.socket.send_string(f"{topic} {message}")


class ZMQReplier:
    def __init__(self, context: zmq.Context, endpoint: str):
        self.socket = context.socket(zmq.REP)
        self.socket.bind(endpoint)

    def receive(self) -> Dict[str, Any]:
        return self.socket.recv_json()

    def reply(self, message: Dict[str, Any]) -> None:
        self.socket.send_json(message)


class MessageRouter:
    def __init__(self):
        self.handlers = {}

    def register(self, topic: str, handler):
        self.handlers[topic] = handler

    def route(self, topic: str, message: Any):
        if topic in self.handlers:
            return self.handlers[topic](message)
        return None


class GestorCarga:
    def __init__(self, context: zmq.Context):
        self.context = context
        self.publisher = ZMQPublisher(context, "tcp://*:5556")
        self.replier = ZMQReplier(context, "tcp://*:5555")
        self.router = MessageRouter()
        self.actores: Dict[str, Any] = {}

    def recibir_peticion(self) -> SimpleNamespace:
        msg = self.replier.receive()
        # Siempre se espera 'operacion', 'isbn' y 'usuario'
        operacion = msg.get("operacion")
        isbn = msg.get("isbn")
        usuario = msg.get("usuario")
        pid = msg.get("id", "")

        payload = {
            "operacion": operacion,
            "isbn": isbn,
            "usuario": usuario
        }

        pet = SimpleNamespace(id=pid, payload=payload, raw=msg)
        return pet

    def publicar_evento(self, topic: str, mensaje: Dict[str, Any]) -> None:
        self.publisher.publish(topic, json.dumps(mensaje))

    def enrutar_prestamo(self, peticion: SimpleNamespace) -> Respuesta:
        operacion = peticion.payload.get("operacion", "desconocida")
        if operacion == "renovacion":
            # construir la respuesta inmediata con nueva fecha = ahora + 7 días
            nueva_fecha = (datetime.now() + timedelta(days=7)).isoformat()
            # Crear una Respuesta usando el constructor dataclass
            resp = Respuesta(
                topico="renovacion", 
                contenido="respuesta", 
                exito=True,
                mensaje="ACEPTADO", 
                fechaOperacion=datetime.now().isoformat(),
                datos={"nueva_fecha": nueva_fecha}
            )
            return resp
        if operacion == "devolucion":
            # vía pub/sub
            self.publicar_evento(operacion, peticion.raw if hasattr(peticion, 'raw') else {"payload": peticion.payload})
            return Respuesta(
                topico="devolucion",
                contenido="respuesta",
                exito=True, 
                mensaje="Devolución enviada a procesamiento", 
                datos={}
            )

        if operacion == "consulta":
            # simplificado: responder directamente
            return Respuesta(
                topico="consulta",
                contenido="respuesta",
                exito=True, 
                mensaje="Consulta recibida", 
                datos=peticion.payload
            )

        if operacion == "prestamo":
            # Enviar préstamo por PUB/SUB (como devolución)
            print("[Gestor] Procesando préstamo...")
            mensaje = peticion.raw if hasattr(peticion, 'raw') else {"payload": peticion.payload}
            print(f"[Gestor] Publicando evento 'prestamo': {mensaje}")
            self.publicar_evento(operacion, mensaje)
            print("[Gestor] Evento publicado, creando respuesta...")
            respuesta = Respuesta(
                topico="prestamo",
                contenido="respuesta",
                exito=True, 
                mensaje="Préstamo enviado a procesamiento", 
                datos={}
            )
            print(f"[Gestor] Respuesta creada: {respuesta}")
            return respuesta

        return Respuesta(
            topico="error",
            contenido="respuesta",
            exito=False, 
            mensaje=f"Operación no soportada: {operacion}", 
            datos={}
        )

    def responder_cliente(self, respuesta: Respuesta) -> None:
        respuesta_dict = respuesta.to_dict() if hasattr(respuesta, 'to_dict') else respuesta.__dict__
        print(f"[Gestor] Enviando respuesta: {respuesta_dict}")
        self.replier.reply(respuesta_dict)
        print("[Gestor] Respuesta enviada")


def main():
    context = zmq.Context()
    gestor = GestorCarga(context)

    print("Gestor listo en puertos 5555 (REQ/REP) y 5556 (PUB/SUB)")

    try:
        while True:
            peticion = gestor.recibir_peticion()#siempre se estan recibiendo peticiones
            print(f"[Gestor] Recibida petición: {peticion.payload}")

            # enrutar según tipo
            print(f"[Gestor] Enrutando operación: {peticion.payload.get('operacion')}")
            respuesta = gestor.enrutar_prestamo(peticion)
            print(f"[Gestor] Respuesta generada: exito={respuesta.exito}, mensaje={respuesta.mensaje}")

            # responder al cliente
            gestor.responder_cliente(respuesta)

            # si fue una renovación, publicar el evento justo después de responder
            if peticion.payload.get("operacion") == "renovacion":
                mensaje = peticion.raw if hasattr(peticion, 'raw') else {"payload": peticion.payload}
                gestor.publicar_evento("renovacion", mensaje)

    except KeyboardInterrupt:
        print("Interrumpido")
    finally:
        context.term()


if __name__ == "__main__":
    main()
