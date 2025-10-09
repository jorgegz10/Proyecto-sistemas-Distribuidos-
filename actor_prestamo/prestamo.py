import zmq
import json
from common.actors.base import Actor


class ActorPrestamo(Actor):
    topic = "prestamo"

    def handle(self, msg: dict) -> dict:
        print(f"[ActorPrestamo] Procesando: {msg}")
        # Simulación: siempre aprueba si el payload tiene isbn
        data = msg.get("payload") if isinstance(msg, dict) else msg
        if isinstance(data, dict):
            if data.get("data") and (data.get("data").get("isbn") or data.get("data").get("titulo") or data.get("isbn")):
                return {"ok": True, "accion": "registrar_prestamo"}
        return {"ok": False, "accion": "datos_invalidos"}


def main():
    context = zmq.Context()

    # SUB socket para eventos pub/sub
    socket_sub = context.socket(zmq.SUB)
    socket_sub.connect("tcp://gestor_carga:5556")
    socket_sub.setsockopt_string(zmq.SUBSCRIBE, ActorPrestamo.topic)

    # REP socket para peticiones síncronas de gestor
    socket_rep = context.socket(zmq.REP)
    socket_rep.bind("tcp://*:5560")

    poller = zmq.Poller()
    poller.register(socket_sub, zmq.POLLIN)
    poller.register(socket_rep, zmq.POLLIN)

    print("[ActorPrestamo] Esperando mensajes... (PUB/SUB y REP en 5560)")

    actor = ActorPrestamo()

    while True:
        events = dict(poller.poll())
        if socket_sub in events:
            raw = socket_sub.recv_string()
            topic, data = raw.split(" ", 1)
            msg = json.loads(data)
            result = actor.handle(msg)
            print(f"[ActorPrestamo] Evento resultado: {result}")

        if socket_rep in events:
            try:
                req = socket_rep.recv_json()
                result = actor.handle(req)
                socket_rep.send_json(result)
                print(f"[ActorPrestamo] Req/Rep resultado: {result}")
            except Exception as e:
                socket_rep.send_json({"ok": False, "error": str(e)})


if __name__ == "__main__":
    main()
