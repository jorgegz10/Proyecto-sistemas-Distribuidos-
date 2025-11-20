import zmq
import json
import sys

def enviar_peticion(socket, operacion, isbn, usuario="test_user"):
    mensaje = {
        "operacion": operacion,
        "isbn": isbn,
        "usuario": usuario
    }
    print(f"\n>> Enviando: {mensaje}")
    socket.send_json(mensaje)
    
    respuesta = socket.recv_json()
    print(f"<< Respuesta: {json.dumps(respuesta, indent=2)}")
    return respuesta

def main():
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect("tcp://localhost:5555")
    
    print("=== Cliente ZMQ conectado al Gestor de Carga (puerto 5555) ===\n")
    
    try:
        if len(sys.argv) < 3:
            print("Uso: python test_cliente.py <operacion> <isbn> [usuario]")
            print("Operaciones: prestamo, consulta, devolucion, renovacion")
            return
        
        operacion = sys.argv[1]
        isbn = sys.argv[2]
        usuario = sys.argv[3] if len(sys.argv) > 3 else "test_user"
        
        enviar_peticion(socket, operacion, isbn, usuario)
    
    finally:
        socket.close()
        context.term()

if __name__ == "__main__":
    main()
