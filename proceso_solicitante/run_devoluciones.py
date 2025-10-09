import zmq
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEVOS = ROOT / "devoluciones.txt"  # 

def leer_devoluciones(path: Path):
    """
    Lee devoluciones en formato:
      DEVO <isbn> <usuario>
    Ignora líneas vacías y comentarios (# ...).
    """
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 3 and parts[0].upper() == "DEVO":
                yield parts[1], parts[2]
            elif len(parts) == 2 and parts[0].upper() == "DEVO":
                # Formato antiguo sin usuario (fallback)
                yield parts[1], "usuario_demo"

def main():
    context = zmq.Context()
    socket_req = context.socket(zmq.REQ)
    socket_req.connect("tcp://gestor_carga:5555")

    if not DEVOS.exists():
        raise SystemExit(f"[run_devoluciones] No existe {DEVOS}. Crea el archivo con líneas 'DEVO <isbn> <usuario>'.")

    print("=== Iniciando envío de devoluciones ===\n")
    for isbn, usuario in leer_devoluciones(DEVOS):
        pet = {
            "operacion": "devolucion",  # en minúscula, como espera el GC
            "isbn": isbn,
            "usuario": usuario,
            "id": f"{isbn}_{usuario}",
        }
        print(f"📤 Enviando devolución: ISBN={isbn}, Usuario={usuario}")
        socket_req.send_json(pet)
        try:
            resp = socket_req.recv_json()
            print(f"📥 Respuesta: {json.dumps(resp, indent=2, ensure_ascii=False)}")
            print("-" * 60)
        except Exception as e:
            print(f"❌ Error al recibir respuesta: {e}")
            print("-" * 60)

    print("\n=== Fin del envío de devoluciones ===")
    socket_req.close()
    context.term()

if __name__ == "__main__":
    main()
