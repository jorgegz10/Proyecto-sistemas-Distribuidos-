#!/usr/bin/env python3
"""
Script para probar el sistema de préstamos, renovaciones y devoluciones
"""
import zmq
import json
import time

def conectar_gestor_carga():
    """Conecta al gestor de carga"""
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect("tcp://localhost:5555")
    socket.setsockopt(zmq.RCVTIMEO, 5000)  # 5 segundos de timeout
    return socket

def enviar_peticion(socket, operacion, isbn, usuario):
    """Envía una petición y espera respuesta"""
    peticion = {
        "operacion": operacion,
        "isbn": isbn,
        "usuario": usuario
    }
    print(f"\n📤 Enviando petición: {operacion}")
    print(f"   ISBN: {isbn}, Usuario: {usuario}")
    
    socket.send_json(peticion)
    respuesta = socket.recv_json()
    
    print("📥 Respuesta recibida:")
    print(f"   {json.dumps(respuesta, indent=2, ensure_ascii=False)}")
    
    return respuesta

def main():
    print("=" * 70)
    print("🧪 PRUEBA DEL SISTEMA DE BIBLIOTECA")
    print("=" * 70)
    
    socket = conectar_gestor_carga()
    
    # Datos de prueba
    isbn = "978-0134685991"
    usuario = "usuario001"
    
    print(f"\n📚 Libro: {isbn}")
    print(f"👤 Usuario: {usuario}")
    
    # ========== PRUEBA 1: PRÉSTAMO ==========
    print("\n" + "="*70)
    print("🔵 PRUEBA 1: PRÉSTAMO DE LIBRO")
    print("="*70)
    
    enviar_peticion(socket, "prestamo", isbn, usuario)
    time.sleep(2)  # Esperar a que se procese
    
    # ========== PRUEBA 2: RENOVACIÓN ==========
    print("\n" + "="*70)
    print("🟡 PRUEBA 2: RENOVACIÓN DE PRÉSTAMO")
    print("="*70)
    
    enviar_peticion(socket, "renovacion", isbn, usuario)
    time.sleep(2)
    
    # ========== PRUEBA 3: SEGUNDA RENOVACIÓN ==========
    print("\n" + "="*70)
    print("🟠 PRUEBA 3: SEGUNDA RENOVACIÓN (máximo 2)")
    print("="*70)
    
    enviar_peticion(socket, "renovacion", isbn, usuario)
    time.sleep(2)
    
    # ========== PRUEBA 4: TERCERA RENOVACIÓN (debe fallar) ==========
    print("\n" + "="*70)
    print("🔴 PRUEBA 4: TERCERA RENOVACIÓN (debe fallar)")
    print("="*70)
    
    enviar_peticion(socket, "renovacion", isbn, usuario)
    time.sleep(2)
    
    # ========== PRUEBA 5: DEVOLUCIÓN ==========
    print("\n" + "="*70)
    print("🟢 PRUEBA 5: DEVOLUCIÓN DE LIBRO")
    print("="*70)
    
    enviar_peticion(socket, "devolucion", isbn, usuario)
    time.sleep(2)
    
    # ========== PRUEBA 6: NUEVO PRÉSTAMO DESPUÉS DE DEVOLUCIÓN ==========
    print("\n" + "="*70)
    print("🔵 PRUEBA 6: NUEVO PRÉSTAMO (después de devolución)")
    print("="*70)
    
    isbn2 = "978-0135957059"
    enviar_peticion(socket, "prestamo", isbn2, usuario)
    
    time.sleep(2)
    
    # Cerrar conexión
    socket.close()
    
    print("\n" + "="*70)
    print("✅ PRUEBAS COMPLETADAS")
    print("="*70)
    print("\n💡 Ahora puedes verificar la base de datos con:")
    print("   docker exec -it postgres_library psql -U app -d library -c \"SELECT * FROM libros;\"")
    print("   docker exec -it postgres_library psql -U app -d library -c \"SELECT * FROM prestamos;\"")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Prueba interrumpida por el usuario")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
