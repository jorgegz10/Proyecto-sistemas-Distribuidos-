import zmq
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOLICITUDES = ROOT / "solicitudes.txt"

def leer_renovaciones(path: Path):
    """Lee solicitudes.txt y extrae renovaciones en formato: RENO isbn usuario"""
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 3 and parts[0].upper() == "RENO":
                isbn = parts[1]
                usuario = parts[2]
                yield (isbn, usuario)
            elif len(parts) == 2 and parts[0].upper() == "RENO":
                # Formato antiguo sin usuario
                yield (parts[1], "usuario_demo")

def main():
    context = zmq.Context()
    socket_req = context.socket(zmq.REQ)
    socket_req.connect("tcp://gestor_carga:5555")

    print("=== Iniciando envío de renovaciones ===\n")
    for isbn, usuario in leer_renovaciones(SOLICITUDES):
        pet = {"operacion": "renovacion", "isbn": isbn, "usuario": usuario, "id": f"{isbn}_{usuario}"}
        print(f"📤 Enviando renovación: ISBN={isbn}, Usuario={usuario}")
        socket_req.send_json(pet)
        try:
            resp = socket_req.recv_json()
            print(f"📥 Respuesta: {json.dumps(resp, indent=2)}")
            print("-" * 60)
        except Exception as e:
            print(f"❌ Error al recibir respuesta: {e}")
            print("-" * 60)

    print("\n=== Fin del envío de renovaciones ===")
    socket_req.close()
    context.term()

if __name__ == "__main__":
    main()
