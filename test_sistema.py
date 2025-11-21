#!/usr/bin/env python3
"""
Script para probar el sistema de préstamos, renovaciones y devoluciones
"""
import zmq
import json
import time
import sys
import os

def conectar_gestor_carga(host="localhost"):
    """Conecta al gestor de carga"""
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    
    # Permitir configurar via variable de entorno o parámetro
    gestor_host = os.getenv("GESTOR_CARGA_HOST", host)
    gestor_port = os.getenv("GESTOR_CARGA_PORT", "5555")
    addr = f"tcp://{gestor_host}:{gestor_port}"
    
    print(f"🔌 Conectando a gestor de carga en: {addr}")
    socket.connect(addr)
    socket.setsockopt(zmq.RCVTIMEO, 10000)  # 10 segundos de timeout
    socket.setsockopt(zmq.SNDTIMEO, 10000)  # 10 segundos de timeout para envío
    socket.setsockopt(zmq.LINGER, 0)  # No esperar al cerrar
    return socket, context

def enviar_peticion(socket, operacion, isbn, usuario, reintentos=2):
    """Envía una petición y espera respuesta con manejo de errores"""
    peticion = {
        "operacion": operacion,
        "isbn": isbn,
        "usuario": usuario
    }
    print(f"\n📤 Enviando petición: {operacion}")
    print(f"   ISBN: {isbn}, Usuario: {usuario}")
    
    for intento in range(reintentos):
        try:
            socket.send_json(peticion)
            respuesta = socket.recv_json()
            
            print("📥 Respuesta recibida:")
            print(f"   {json.dumps(respuesta, indent=2, ensure_ascii=False)}")
            
            return respuesta
            
        except zmq.error.Again:
            print(f"⚠️  Timeout esperando respuesta (intento {intento + 1}/{reintentos})")
            if intento < reintentos - 1:
                # Recrear socket para el siguiente intento
                socket.close()
                context = zmq.Context()
                socket = context.socket(zmq.REQ)
                gestor_host = os.getenv("GESTOR_CARGA_HOST", "localhost")
                gestor_port = os.getenv("GESTOR_CARGA_PORT", "5555")
                socket.connect(f"tcp://{gestor_host}:{gestor_port}")
                socket.setsockopt(zmq.RCVTIMEO, 10000)
                socket.setsockopt(zmq.SNDTIMEO, 10000)
                socket.setsockopt(zmq.LINGER, 0)
                time.sleep(1)
            else:
                print("❌ Servicio no responde - continuando con siguiente prueba")
                return {"error": "Timeout", "exito": False, "mensaje": "Servicio no disponible"}
                
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            if intento < reintentos - 1:
                time.sleep(1)
            else:
                return {"error": str(e), "exito": False, "mensaje": "Error de conexión"}
    
    return None

def main():
    print("=" * 70)
    print("🧪 PRUEBA DEL SISTEMA DE BIBLIOTECA")
    print("=" * 70)
    
    # Obtener host del gestor de carga desde argumentos o usar localhost
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    
    try:
        socket, context = conectar_gestor_carga(host)
    except Exception as e:
        print(f"❌ Error al conectar: {e}")
        return
    
    # Datos de prueba
    isbn = "978-0596007126"
    usuario = "usuario005"
    
    print(f"\n📚 Libro: {isbn}")
    print(f"👤 Usuario: {usuario}")
    
    try:
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
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Prueba interrumpida por el usuario")
    except Exception as e:
        print(f"\n\n❌ Error durante las pruebas: {e}")
    finally:
        # Cerrar conexión
        try:
            socket.close()
            context.term()
        except Exception:
            pass
    
    print("\n" + "="*70)
    print("✅ PRUEBAS COMPLETADAS")
    print("="*70)
    print("\n💡 Verificar la base de datos con:")
    print("   docker exec -it postgres_primary psql -U app -d library -c \"SELECT * FROM libros;\"")
    print("   docker exec -it postgres_primary psql -U app -d library -c \"SELECT * FROM prestamos;\"")
    print("\n💡 Uso del script:")
    print("   python test_sistema.py                    # Conecta a localhost")
    print("   python test_sistema.py 192.168.1.100      # Conecta a IP específica")
    print("   $env:GESTOR_CARGA_HOST=\"192.168.1.100\"; python test_sistema.py")

if __name__ == "__main__":
    main()
