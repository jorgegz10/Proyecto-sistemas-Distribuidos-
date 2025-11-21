import os
import zmq
import psycopg2                      
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

# Config DB desde variables de entorno
DB_HOST = os.getenv("DB_HOST", "postgres_primary")     
DB_PORT = int(os.getenv("DB_PORT", "5432"))    
DB_STANDBY_HOST = os.getenv("DB_STANDBY_HOST", "postgres_replica")  # Cambiado a postgres_replica
DB_NAME = os.getenv("DB_NAME", "library")      
DB_USER = os.getenv("DB_USER", "app")          
DB_PASS = os.getenv("DB_PASS", "app")

# Estado de conexión global
current_db_host = DB_HOST
current_db_port = DB_PORT
last_failover_time = None


# Helpers de base de datos
def is_connection_read_only(conn):
    # Verifica si la conexión actual es de solo lectura
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW transaction_read_only;")
            result = cur.fetchone()
            return result[0] == 'on' if result else False
    except Exception as e:
        print(f"[DB] Error verificando read-only status: {e}")
        return True  # Asumir read-only si hay error


def connect_db_with_failover(preferred_host=None):
    """
    Conecta a PostgreSQL con soporte para failover automático.
    Intenta conectar al host preferido, si falla intenta el alternativo.
    También prueba diferentes puertos (5432 y 5433).
    Verifica que la conexión sea de escritura (no read-only).
    
    Args:
        preferred_host: Host preferido para conectar (None = usar el actual)
    
    Returns:
        Tupla (conexión, host_usado)
    """
    global current_db_host, current_db_port, last_failover_time
    
    # Lista de (host, puerto) para probar
    hosts_to_try = []
    
    if preferred_host:
        # Si se especifica un host preferido, probar ese primero con ambos puertos
        hosts_to_try.append((preferred_host, DB_PORT))
        hosts_to_try.append((preferred_host, 5433))
    else:
        # Probar host actual primero, luego alternativo
        hosts_to_try.append((current_db_host, current_db_port))
        hosts_to_try.append((DB_STANDBY_HOST, 5432))
        hosts_to_try.append((DB_STANDBY_HOST, 5433))
    
    last_error = None
    for host, port in hosts_to_try:
        try:
            print(f"[DB] Intentando conectar a {host}:{port}")
            conn = psycopg2.connect(
                host=host,
                port=port,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASS,
                connect_timeout=5
            )
            
            # Verificar que no sea read-only
            if not is_connection_read_only(conn):
                print(f"[DB] Conectado exitosamente a {host}:{port}")
                current_db_host = host
                current_db_port = port
                last_failover_time = datetime.now()
                return conn, host
            else:
                print(f"[DB] {host}:{port} es read-only, buscando alternativa...")
                conn.close()
        except Exception as e:
            last_error = e
            print(f"[DB] Fallo conexión a {host}:{port}: {e}")
    
    # Si llegamos aquí, ninguna conexión funcionó
    print(f"[DB] ERROR: No se pudo conectar a ningún servidor")
    raise Exception(f"No se pudo conectar a la base de datos: {last_error}")


def connect_db():
    """Conecta a la base de datos con soporte de failover."""
    conn, _ = connect_db_with_failover()
    return conn


def reconnect_db_if_needed(conn):
    """
    Verifica si la conexión está activa, si no, intenta reconectar.
    
    Returns:
        Nueva conexión si fue necesario reconectar, o la misma si está ok.
    """
    try:
        # Test rápido de la conexión
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
        return conn
    except Exception as e:
        print(f"[DB] Conexión perdida: {e}. Intentando reconectar...")
        try:
            conn.close()
        except Exception:
            pass
        
        # Intentar reconectar con failover
        new_conn, _ = connect_db_with_failover()
        return new_conn


def ensure_schema(conn):                        
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS libros (
          isbn TEXT PRIMARY KEY,
          ejemplares INTEGER NOT NULL DEFAULT 0
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS prestamos (
          isbn TEXT NOT NULL,
          usuario TEXT NOT NULL,
          estado TEXT NOT NULL DEFAULT 'ACTIVO',
          fecha_devolucion TIMESTAMPTZ,
          renovaciones INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY (isbn, usuario)
        );
        """)
    conn.commit()


def validar_renovacion(conn, isbn, usuario):    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT renovaciones FROM prestamos WHERE isbn=%s AND usuario=%s;",
            (isbn, usuario)
        )
        row = cur.fetchone()
        return {"renovaciones": (row["renovaciones"] if row else 0)}


def actualizar_renovacion(conn, isbn, usuario, nueva_fecha=None):
    """
    Actualiza una renovación de préstamo.
    Que no se exceda 2 renovaciones.

    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Verificar préstamo existente
            cur.execute(
                "SELECT renovaciones, estado, fecha_devolucion FROM prestamos WHERE isbn=%s AND usuario=%s;",
                (isbn, usuario)
            )
            prestamo = cur.fetchone()
            
            if not prestamo:
                return {
                    "error": "PrestamoNoEncontrado",
                    "detalle": f"No existe un préstamo para el usuario {usuario} del libro {isbn}"
                }
            
            if prestamo["estado"] != "ACTIVO":
                return {
                    "error": "PrestamoNoActivo",
                    "detalle": f"El préstamo no está activo (estado: {prestamo['estado']})"
                }
            
            # Validar límite de renovaciones
            if prestamo["renovaciones"] >= 2:
                return {
                    "error": "LimiteRenovaciones",
                    "detalle": f"Se alcanzó el límite de 2 renovaciones (actual: {prestamo['renovaciones']})"
                }
            
            # Calcular nueva fecha de devolución (+7 días desde la actual)
            if nueva_fecha is None:
                fecha_actual = prestamo["fecha_devolucion"]
                nueva_fecha_calculada = fecha_actual + timedelta(days=7)
            else:
                nueva_fecha_calculada = nueva_fecha
            
            # Actualizar préstamo
            cur.execute("""
                UPDATE prestamos
                SET fecha_devolucion = %s,
                    renovaciones = renovaciones + 1
                WHERE isbn=%s AND usuario=%s;
            """, (nueva_fecha_calculada, isbn, usuario))
        
        conn.commit()
        
        return {
            "status": "ok",
            "detalle": "Renovación completada exitosamente",
            "datos": {
                "isbn": isbn,
                "usuario": usuario,
                "nueva_fecha_devolucion": nueva_fecha_calculada.isoformat() if hasattr(nueva_fecha_calculada, 'isoformat') else str(nueva_fecha_calculada),
                "renovaciones": prestamo["renovaciones"] + 1
            }
        }
        
    except Exception as e:
        conn.rollback()
        return {
            "error": "ErrorProcesamiento",
            "detalle": f"Error al procesar renovación: {str(e)}"
        }



def consultar_libro(conn, isbn):
    # Consulta si un libro existe y retorna sus datos
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM libros WHERE isbn=%s;", (isbn,))
            libro = cur.fetchone()
            
            if libro:
                return {"status": "ok", "datos": libro}
            else:
                return {"error": "LibroNoEncontrado", "detalle": f"El libro {isbn} no existe"}
    except Exception as e:
        return {"error": "ErrorConsulta", "detalle": str(e)}


def aplicar_devolucion(conn, isbn, usuario):    
    try:
        with conn.cursor() as cur:
            # Marcar préstamo como DEVUELTO; si no existe, se cre como DEVUELTO
            cur.execute("""
                UPDATE prestamos
                   SET estado='DEVUELTO', fecha_devolucion=NOW()
                 WHERE isbn=%s AND usuario=%s;
            """, (isbn, usuario))
            if cur.rowcount == 0:
                cur.execute("""
                    INSERT INTO prestamos (isbn, usuario, estado, fecha_devolucion, renovaciones)
                    VALUES (%s, %s, 'DEVUELTO', NOW(), 0)
                    ON CONFLICT (isbn, usuario) DO NOTHING;
                """, (isbn, usuario))

            # Incrementar ejemplares del libro 
            cur.execute("""
                INSERT INTO libros(isbn, ejemplares)
                VALUES (%s, 1)
                ON CONFLICT (isbn)
                DO UPDATE SET ejemplares = libros.ejemplares + 1;
            """, (isbn,))

        conn.commit()
        return {"status": "ok", "detalle": "devolucion completada"}
    except Exception as e:
        conn.rollback()
        return {"error": str(e)}


def procesar_prestamo(conn, isbn, usuario):
    """
    Procesa un nuevo préstamo de libro.
    Verifica ejemplares disponibles y crea el préstamo.
    
    Args:
        conn: Conexión a la base de datos
        isbn: ISBN del libro a prestar
        usuario: ID/nombre del usuario
    
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Verificar que el libro existe y tiene ejemplares disponibles
            cur.execute(
                "SELECT ejemplares FROM libros WHERE isbn=%s;",
                (isbn,)
            )
            libro = cur.fetchone()
            
            if not libro:
                return {
                    "error": "LibroNoEncontrado",
                    "detalle": f"El libro con ISBN {isbn} no existe en el sistema"
                }
            
            if libro["ejemplares"] <= 0:
                return {
                    "error": "SinEjemplaresDisponibles",
                    "detalle": f"No hay ejemplares disponibles del libro {isbn}"
                }
            
            # Verificar que el usuario no tenga ya un préstamo activo de este libro
            cur.execute(
                "SELECT estado FROM prestamos WHERE isbn=%s AND usuario=%s;",
                (isbn, usuario)
            )
            prestamo_existente = cur.fetchone()
            
            if prestamo_existente and prestamo_existente["estado"] == "ACTIVO":
                return {
                    "error": "PrestamoActivo",
                    "detalle": f"El usuario {usuario} ya tiene un préstamo activo del libro {isbn}"
                }
            
            # Calcular fecha de devolución (14 días desde hoy)
            fecha_prestamo = datetime.now()
            fecha_devolucion = fecha_prestamo + timedelta(days=14)
            
            # Crear o actualizar el préstamo
            cur.execute("""
                INSERT INTO prestamos (isbn, usuario, estado, fecha_devolucion, renovaciones)
                VALUES (%s, %s, 'ACTIVO', %s, 0)
                ON CONFLICT (isbn, usuario)
                DO UPDATE SET estado='ACTIVO', 
                              fecha_devolucion=%s,
                              renovaciones=0;
            """, (isbn, usuario, fecha_devolucion, fecha_devolucion))
            
            # Decrementar ejemplares disponibles
            cur.execute("""
                UPDATE libros 
                SET ejemplares = ejemplares - 1
                WHERE isbn=%s;
            """, (isbn,))
        
        conn.commit()
        
        return {
            "status": "ok",
            "detalle": "Préstamo registrado exitosamente",
            "datos": {
                "isbn": isbn,
                "usuario": usuario,
                "fecha_prestamo": fecha_prestamo.isoformat(),
                "fecha_devolucion": fecha_devolucion.isoformat(),
                "dias_prestamo": 14
            }
        }
        
    except Exception as e:
        conn.rollback()
        return {
            "error": "ErrorProcesamiento",
            "detalle": f"Error al procesar préstamo: {str(e)}"
        }


# ZMQ REP Server 
def main():
    # ZMQ
    context = zmq.Context()
    socket_rep = context.socket(zmq.REP)
    socket_rep.bind("tcp://*:5570")

    print("[GestorAlmacenamiento] Escuchando en 5570 (REP) - Postgres con failover automático")  

    # Conexión y esquema
    conn = connect_db()
    print(f"[GestorAlmacenamiento] Conectado a PostgreSQL ({current_db_host})")
    ensure_schema(conn)
    print("[GestorAlmacenamiento] Esquema de base de datos verificado")
    print("[GestorAlmacenamiento] Listo para recibir peticiones...")

    request_count = 0
    while True:
        try:
            # Verificar conexión cada 10 requests
            request_count += 1
            if request_count % 10 == 0:
                conn = reconnect_db_if_needed(conn)
            
            req = socket_rep.recv_json()

            # Acepta "action" o "accion"
            action = req.get("action") or req.get("accion")  

            if action == "validar_renovacion":
                isbn = req.get("isbn"); usuario = req.get("usuario")
                resp = validar_renovacion(conn, isbn, usuario)

            elif action == "actualizar_renovacion":
                isbn = req.get("isbn"); usuario = req.get("usuario")
                nueva_fecha = req.get("nueva_fecha") or datetime.now().isoformat()
                resp = actualizar_renovacion(conn, isbn, usuario, nueva_fecha)

            elif action == "aplicar_devolucion":
                isbn = req.get("isbn"); usuario = req.get("usuario")
                if not isbn or not usuario:
                    resp = {"error": "ParametrosInvalidos"}
                else:
                    resp = aplicar_devolucion(conn, isbn, usuario)

            elif action == "procesar_prestamo":
                isbn = req.get("isbn"); usuario = req.get("usuario")
                if not isbn or not usuario:
                    resp = {"error": "ParametrosInvalidos", "detalle": "ISBN y usuario son requeridos"}
                else:
                    resp = procesar_prestamo(conn, isbn, usuario)

            elif action == "consultar_libro":
                isbn = req.get("isbn")
                if not isbn:
                    resp = {"error": "ParametrosInvalidos"}
                else:
                    resp = consultar_libro(conn, isbn)

            else:
                resp = {"error": "accion_desconocida"}

            socket_rep.send_json(resp)

        except psycopg2.OperationalError as e:
            # Error de conexión - intentar reconectar
            print(f"[DB] Error de conexión a la base de datos: {e}")
            try:
                conn = connect_db()
                print(f"[DB] Reconexión exitosa a {current_db_host}")
                socket_rep.send_json({
                    "error": "ErrorConexionDB",
                    "detalle": "Se perdió la conexión a la base de datos, reintente la operación"
                })
            except Exception as reconnect_error:
                print(f"[DB] Fallo la reconexión: {reconnect_error}")
                socket_rep.send_json({
                    "error": "ErrorConexionDB",
                    "detalle": f"No se pudo reconectar a la base de datos: {str(reconnect_error)}"
                })
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[ERROR] Excepción no manejada: {e}")
            try:
                socket_rep.send_json({"error": str(e)})
            except Exception:
                pass

    try:
        conn.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()
