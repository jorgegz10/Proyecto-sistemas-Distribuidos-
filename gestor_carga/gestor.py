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

    def receive(self):
        message = self.socket.recv_json()
        return None, message

    def reply(self, identity, message: Dict[str, Any]) -> None:
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
        _, msg = self.replier.receive()
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

    def _consultar_almacenamiento(self, peticion: dict) -> dict:
        """Realiza una petición síncrona al gestor de almacenamiento"""
        try:
            req = self.context.socket(zmq.REQ)
            req.RCVTIMEO = 5000
            req.SNDTIMEO = 5000
            req.connect("tcp://gestor_almacenamiento:5570")
            req.send_json(peticion)
            response = req.recv_json()
            req.close()
            return response
        except Exception as e:
            print(f"[Gestor] Error al consultar almacenamiento: {e}")
            return {"error": "ErrorComunicacion", "detalle": str(e)}

    def enrutar_prestamo(self, peticion: SimpleNamespace) -> Respuesta:
        operacion = peticion.payload.get("operacion", "desconocida")
        isbn = peticion.payload.get("isbn")
        usuario = peticion.payload.get("usuario")
        
        if operacion == "prestamo":
            print("[Gestor] Procesando préstamo...")
            req = None
            try:
                req = self.context.socket(zmq.REQ)
                req.setsockopt(zmq.RCVTIMEO, 5000)
                req.setsockopt(zmq.SNDTIMEO, 5000)
                req.setsockopt(zmq.LINGER, 0)
                req.connect("tcp://actor_prestamo:5560")
                
                req.send_json({"isbn": isbn, "usuario": usuario})
                response = req.recv_json()
                
                print(f"[Gestor] Respuesta del actor: {response}")
                
                if response.get("exito"):
                    return Respuesta(
                        topico="prestamo",
                        contenido="respuesta",
                        exito=True,
                        mensaje="Préstamo registrado exitosamente",
                        datos=response.get("prestamo", {})
                    )
                else:
                    return Respuesta(
                        topico="prestamo",
                        contenido="respuesta",
                        exito=False,
                        mensaje=response.get("error", "Error al procesar préstamo"),
                        datos={"error": response.get("detalle")}
                    )
            except zmq.error.Again:
                print(f"[Gestor] Timeout esperando respuesta del actor de préstamo")
                return Respuesta(
                    topico="prestamo",
                    contenido="respuesta",
                    exito=False,
                    mensaje="Servicio de préstamo no disponible",
                    datos={}
                )
            except Exception as e:
                print(f"[Gestor] Error: {e}")
                return Respuesta(
                    topico="prestamo",
                    contenido="respuesta",
                    exito=False,
                    mensaje=f"Error al procesar préstamo: {str(e)}",
                    datos={}
                )
            finally:
                if req:
                    req.close()
                
        elif operacion == "renovacion":
            print("[Gestor] Procesando renovación...")
            req = None
            try:
                req = self.context.socket(zmq.REQ)
                req.setsockopt(zmq.RCVTIMEO, 5000)
                req.setsockopt(zmq.SNDTIMEO, 5000)
                req.setsockopt(zmq.LINGER, 0)
                req.connect("tcp://actor_renovacion:5561")
                
                req.send_json({"isbn": isbn, "usuario": usuario})
                response = req.recv_json()
                
                print(f"[Gestor] Respuesta del actor: {response}")
                
                if response.get("exito"):
                    return Respuesta(
                        topico="renovacion",
                        contenido="respuesta",
                        exito=True,
                        mensaje="Renovación completada exitosamente",
                        datos=response.get("renovacion", {})
                    )
                else:
                    return Respuesta(
                        topico="renovacion",
                        contenido="respuesta",
                        exito=False,
                        mensaje=response.get("error", "Error al renovar"),
                        datos={}
                    )
            except zmq.error.Again:
                print("[Gestor] Timeout esperando respuesta del actor de renovación")
                return Respuesta(
                    topico="renovacion",
                    contenido="respuesta",
                    exito=False,
                    mensaje="Servicio de renovación no disponible",
                    datos={}
                )
            except Exception as e:
                print(f"[Gestor] Error: {e}")
                return Respuesta(
                    topico="renovacion",
                    contenido="respuesta",
                    exito=False,
                    mensaje=f"Error al procesar renovación: {str(e)}",
                    datos={}
                )
            finally:
                if req:
                    req.close()
                
        elif operacion == "devolucion":
            print("[Gestor] Procesando devolución...")
            req = None
            try:
                req = self.context.socket(zmq.REQ)
                req.setsockopt(zmq.RCVTIMEO, 5000)
                req.setsockopt(zmq.SNDTIMEO, 5000)
                req.setsockopt(zmq.LINGER, 0)
                req.connect("tcp://actor_devolucion:5562")
                
                req.send_json({"isbn": isbn, "usuario": usuario})
                response = req.recv_json()
                
                print(f"[Gestor] Respuesta del actor: {response}")
                
                if response.get("exito"):
                    return Respuesta(
                        topico="devolucion",
                        contenido="respuesta",
                        exito=True,
                        mensaje="Devolución procesada exitosamente",
                        datos={}
                    )
                else:
                    return Respuesta(
                        topico="devolucion",
                        contenido="respuesta",
                        exito=False,
                        mensaje=response.get("error", "Error al procesar devolución"),
                        datos={}
                    )
            except zmq.error.Again:
                print("[Gestor] Timeout esperando respuesta del actor de devolución")
                return Respuesta(
                    topico="devolucion",
                    contenido="respuesta",
                    exito=False,
                    mensaje="Servicio de devolución no disponible",
                    datos={}
                )
            except Exception as e:
                print(f"[Gestor] Error: {e}")
                return Respuesta(
                    topico="devolucion",
                    contenido="respuesta",
                    exito=False,
                    mensaje=f"Error al procesar devolución: {str(e)}",
                    datos={}
                )
            finally:
                if req:
                    req.close()

        elif operacion == "consulta":
            return Respuesta(
                topico="consulta",
                contenido="respuesta",
                exito=True, 
                mensaje="Consulta recibida", 
                datos=peticion.payload
            )

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
        self.replier.reply(None, respuesta_dict)
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

    except KeyboardInterrupt:
        print("Interrumpido")
    finally:
        context.term()


if __name__ == "__main__":
    main()
