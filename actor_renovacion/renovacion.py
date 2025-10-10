import os
import zmq
import json
from typing import Dict, Any
from common.actors.base import Actor


class ActorRenovacion(Actor):
    topic = "renovacion"

    def handle(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        # Espera un mensaje con keys: isbn, usuario, nueva_fecha
        print(f"[ActorRenovacion] Procesando mensaje: {msg}")
        data = msg.get("payload") if isinstance(msg, dict) else msg
        # Validación simple: comprobar campos mínimos
        isbn = None
        usuario = None
        nueva_fecha = None
        if isinstance(data, dict):
            isbn = data.get("isbn") or data.get("data", {}).get("isbn")
            usuario = data.get("usuario") or data.get("data", {}).get("usuario")
            nueva_fecha = data.get("nueva_fecha") or data.get("data", {}).get("nueva_fecha")

        if isbn and usuario and nueva_fecha:
            # Validar con el gestor de almacenamiento si la renovación es permitida
            try:
                permitido = self.validarRenovacion(isbn, usuario)
                if permitido:
                    # proceder a actualizar la renovación en el gestor de almacenamiento
                    try:
                        resp = self.actualizarRenovacion(isbn, usuario, nueva_fecha)
                        # espera {"status": "ok", "detalle": "renovacion completada"}
                        if isinstance(resp, dict) and resp.get("status") == "ok":
                            print(f"renovacion procesada: {resp}")
                            return {"ok": True, "accion": "renovar_prestamo", "nueva_fecha": nueva_fecha}
                        else:
                            # Propagar error
                            return {"ok": False, "accion": "error_actualizacion", "detalle": resp}
                    except Exception as e:
                        return {"ok": False, "accion": "error_actualizacion", "error": str(e)}
                else:
                    return {"ok": False, "accion": "renovacion_denegada"}
            except Exception as e:
                return {"ok": False, "accion": "error_validacion", "error": str(e)}

        return {"ok": False, "accion": "datos_invalidos"}


def main():
    context = zmq.Context()

    # SUB socket para eventos pub/sub
    socket_sub = context.socket(zmq.SUB)
    # Allow configuring the gestor_carga pub endpoint so this actor can be remote.
    gc_pub_addr = None
    # Check a full address env var first, then host/port pair, then default
    if os.getenv("GESTOR_CARGA_PUB_ADDR"):
        gc_pub_addr = os.getenv("GESTOR_CARGA_PUB_ADDR")
    elif os.getenv("GESTOR_CARGA_HOST") and os.getenv("GESTOR_CARGA_PUB_PORT"):
        gc_pub_addr = f"tcp://{os.getenv('GESTOR_CARGA_HOST')}:{os.getenv('GESTOR_CARGA_PUB_PORT')}"
    else:
        gc_pub_addr = "tcp://gestor_carga:5556"

    print(f"[ActorRenovacion] Conectando PUB/SUB a {gc_pub_addr}")
    socket_sub.connect(gc_pub_addr)
    socket_sub.setsockopt_string(zmq.SUBSCRIBE, ActorRenovacion.topic)

    print("[ActorRenovacion] Suscrito al tópico 'renovacion', esperando mensajes...")

    actor = ActorRenovacion()

    while True:
        try:
            raw = socket_sub.recv_string()
            topic, data = raw.split(" ", 1)
            msg = json.loads(data)
            # recibirMensaje equivale a procesar el mensaje recibido
            result = actor.handle(msg)
            print(f"[ActorRenovacion] Resultado: {result}")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[ActorRenovacion] Error al procesar mensaje: {e}")


    # Método para validar renovaciones con el gestor de almacenamiento
    def validarRenovacion(self, isbn: str, usuario: str) -> bool:
        # Método de instancia ligado a ActorRenovacion; abrirá un REQ temporal
        hosts = ["tcp://gestor_almacenamiento:5570", "tcp://localhost:5570"]
        for host in hosts:
            context = zmq.Context()
            req = context.socket(zmq.REQ)
            req.RCVTIMEO = 3000
            req.SNDTIMEO = 3000
            try:
                req.connect(host)
                req.send_json({"action": "validar_renovacion", "isbn": isbn, "usuario": usuario})
                resp = req.recv_json()
                # según la especificación temporal, resp tiene 'renovaciones'
                renovaciones = resp.get("renovaciones") if isinstance(resp, dict) else None
                # Por ahora la regla es: si renovaciones == 1 -> permitido
                return renovaciones == 1
            except Exception:
                # intentar el siguiente host
                try:
                    req.close()
                except Exception:
                    pass
                continue
        # si todos fallan, levantar excepción
        raise ConnectionError("No se pudo conectar al gestor de almacenamiento en los hosts probados")

    def actualizarRenovacion(self, isbn: str, usuario: str, nueva_fecha: str) -> Dict[str, Any]:
        # Llamada REQ al gestor de almacenamiento para actualizar el registro
        context = zmq.Context()
        req = context.socket(zmq.REQ)
        req.RCVTIMEO = 5000
        req.SNDTIMEO = 5000
        try:
            req.connect("tcp://gestor_almacenamiento:5570")
            req.send_json({"action": "actualizar_renovacion", "isbn": isbn, "usuario": usuario, "nueva_fecha": nueva_fecha})
            resp = req.recv_json()
            # Si el gestor responde con ErrorMaxRenovaciones, notificar al gestor de carga
            if isinstance(resp, dict) and resp.get("error") == "ErrorMaxRenovaciones":
                # notificar al gestor de carga
                try:
                    self.notificarError(usuario, "limite_renovaciones")
                except Exception as e:
                    print(f"Error notificando al gestor de carga: {e}")
            return resp
        finally:
            try:
                req.close()
            except Exception:
                pass

    def notificarError(self, usuario: str, detalle: str) -> None:
        # Enviar notificación al gestor de carga vía REQ/REP (gestor_carga escucha en 5555)
        context = zmq.Context()
        req = context.socket(zmq.REQ)
        req.RCVTIMEO = 3000
        req.SNDTIMEO = 3000
        try:
            req.connect("tcp://gestor_carga:5555")
            req.send_json({"operacion": "error", "usuario": usuario, "detalle": detalle})
            # no esperamos una estructura concreta; se ignora la respuesta o se imprime
            try:
                resp = req.recv_json()
                print(f"Respuesta gestor_carga a notificarError: {resp}")
            except Exception:
                pass
        finally:
            try:
                req.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
