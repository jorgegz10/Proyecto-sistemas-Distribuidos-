import zmq
import json
import os
from typing import Dict, Any, List, Optional
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
        
        # Configurar múltiples endpoints de almacenamiento para failover
        self.storage_endpoints = self._get_storage_endpoints()
        self.current_storage_index = 0
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Inicializar circuit breaker para cada endpoint de almacenamiento
        for endpoint in self.storage_endpoints:
            self.circuit_breakers[endpoint] = CircuitBreaker()
        
        print(f"[Gestor] 🔧 Configurado con {len(self.storage_endpoints)} endpoints de almacenamiento")
        for ep in self.storage_endpoints:
            print(f"[Gestor]    - {ep}")
    
    def _get_storage_endpoints(self) -> List[str]:
        """Obtiene lista de endpoints de almacenamiento (para failover)"""
        # Permite configurar múltiples endpoints via variable de entorno
        # Formato: "host1:port1,host2:port2"
        endpoints_env = os.getenv("GESTOR_ALMACENAMIENTO_ENDPOINTS", "gestor_almacenamiento:5570")
        endpoints = []
        for ep in endpoints_env.split(","):
            ep = ep.strip()
            if "://" not in ep:
                ep = f"tcp://{ep}"
            endpoints.append(ep)
        return endpoints

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
    
    def _connect_to_storage_with_failover(self, request_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Intenta conectar al almacenamiento con failover automático entre endpoints"""
        max_attempts = len(self.storage_endpoints) * 2  # Intentar cada endpoint 2 veces
        
        for attempt in range(max_attempts):
            endpoint = self.storage_endpoints[self.current_storage_index]
            cb = self.circuit_breakers[endpoint]
            
            # Verificar si el circuit breaker está abierto
            if cb.is_open():
                print(f"[Gestor] ⚠️  Circuit breaker ABIERTO para {endpoint}, probando siguiente...")
                self.current_storage_index = (self.current_storage_index + 1) % len(self.storage_endpoints)
                continue
            
            try:
                print(f"[Gestor] 🔄 Conectando a {endpoint} (intento {attempt + 1}/{max_attempts})")
                
                req = self.context.socket(zmq.REQ)
                req.RCVTIMEO = 3000  # 3 segundos timeout
                req.SNDTIMEO = 3000
                req.connect(endpoint)
                
                req.send_json(request_data)
                response = req.recv_json()
                req.close()
                
                # Éxito - resetear circuit breaker
                cb.on_success()
                print(f"[Gestor] ✅ Conexión exitosa a {endpoint}")
                return response
                
            except zmq.Again:
                print(f"[Gestor] ⏱️  Timeout en {endpoint}")
                cb.on_failure()
                try:
                    req.close()
                except:
                    pass
                self.current_storage_index = (self.current_storage_index + 1) % len(self.storage_endpoints)
                
            except Exception as e:
                print(f"[Gestor] ❌ Error en {endpoint}: {e}")
                cb.on_failure()
                try:
                    req.close()
                except:
                    pass
                self.current_storage_index = (self.current_storage_index + 1) % len(self.storage_endpoints)
        
        print("[Gestor] ⛔ TODOS los endpoints de almacenamiento fallaron")
        return None

    def enrutar_prestamo(self, peticion: SimpleNamespace) -> Respuesta:
        operacion = peticion.payload.get("operacion", "desconocida")
        if operacion == "renovacion":
            # Comunicación SÍNCRONA con gestor de almacenamiento CON FAILOVER
            print("[Gestor] 📋 Procesando renovación síncrona con failover...")
            isbn = peticion.payload.get("isbn")
            usuario = peticion.payload.get("usuario")
            
            request_data = {"action": "actualizar_renovacion", "isbn": isbn, "usuario": usuario}
            response = self._connect_to_storage_with_failover(request_data)
            
            if response is None:
                return Respuesta(
                    topico="renovacion",
                    contenido="respuesta",
                    exito=False,
                    mensaje="⛔ Servicio de almacenamiento no disponible (todos los servidores fallaron)",
                    datos={"error": "Failover completo - sin servidores disponibles"}
                )
            
            print(f"[Gestor] Respuesta de almacenamiento: {response}")
            
            if response.get("status") == "ok":
                return Respuesta(
                    topico="renovacion",
                    contenido="respuesta",
                    exito=True,
                    mensaje="Renovación completada exitosamente",
                    datos=response.get("datos", {})
                )
            else:
                return Respuesta(
                    topico="renovacion",
                    contenido="respuesta",
                    exito=False,
                    mensaje=response.get("detalle", "Error al renovar"),
                    datos={"error": response.get("error")}
                )
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

    except KeyboardInterrupt:
        print("Interrumpido")
    finally:
        context.term()


if __name__ == "__main__":
    main()
