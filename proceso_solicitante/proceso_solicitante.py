import os
import zmq
from common.messaging.peticion import Peticion

def mostrar_menu() -> None:
    print("  --- Menú ---")
    print("  1) Préstamo por ISBN")
    print("  2) Préstamo por Título")
    print("  3) Consulta por ISBN")
    print("  4) Devolución por ISBN")
    print("  0) Salir")

def enviarPeticion(socket_req, operacion, data):
    peticion = Peticion(payload={"operacion": operacion, "data": data})
    socket_req.send_json(peticion.__dict__)
    respuesta = socket_req.recv_json()
    print(f"[Solicitante] Respuesta recibida: {respuesta}\n")

def main():
    context = zmq.Context()
    socket_req = context.socket(zmq.REQ)

    # Allow running proceso_solicitante on a different machine by configuring
    # the gestor_carga endpoint through environment variables.
    # Priority: GESTOR_CARGA_ADDR > (GESTOR_CARGA_HOST + GESTOR_CARGA_PORT) > default
    addr = os.getenv("GESTOR_CARGA_ADDR")
    host = os.getenv("GESTOR_CARGA_HOST")
    port = os.getenv("GESTOR_CARGA_PORT")
    if addr:
        connect_addr = addr
    elif host and port:
        connect_addr = f"tcp://{host}:{port}"
    else:
        connect_addr = "tcp://gestor_carga:5555"

    print(f"[Solicitante] Conectando a gestor_carga en {connect_addr}")
    socket_req.connect(connect_addr)

    try:
        while True:
            mostrar_menu()
            opcion = input("Selecciona una opción: ").strip()

            if opcion == "0":
                print("Saliendo...")
                break
            elif opcion == "1":
                isbn = input("ISBN del libro: ").strip()
                enviarPeticion(socket_req, "prestamo", {"isbn": isbn, "usuario": "usuario_demo"})
            elif opcion == "2":
                titulo = input("Título del libro: ").strip()
                enviarPeticion(socket_req, "prestamo", {"titulo": titulo, "usuario": "usuario_demo"})
            elif opcion == "3":
                isbn = input("ISBN para consulta: ").strip()
                enviarPeticion(socket_req, "consulta", {"isbn": isbn})
            elif opcion == "4":
                isbn = input("ISBN para devolución: ").strip()
                enviarPeticion(socket_req, "devolucion", {"isbn": isbn, "usuario": "usuario_demo"})
            else:
                print("Opción no válida.\n")

    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    finally:
        socket_req.close()
        context.term()

if __name__ == "__main__":
    main()
