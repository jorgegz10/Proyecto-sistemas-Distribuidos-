import os
import zmq
import psycopg2                      
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

# === Config DB desde variables de entorno ===
DB_HOST = os.getenv("DB_HOST", "postgres")     
DB_PORT = int(os.getenv("DB_PORT", "5432"))    
DB_NAME = os.getenv("DB_NAME", "library")      
DB_USER = os.getenv("DB_USER", "app")          
DB_PASS = os.getenv("DB_PASS", "app")         


# ===== Helpers de base de datos =====
def connect_db():                               
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )
    conn.autocommit = False
    return conn


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


def actualizar_renovacion(conn, isbn, usuario, nueva_fecha):  
    with conn.cursor() as cur:
        # UPSERT y cap a 2 renovaciones
        cur.execute("""
            INSERT INTO prestamos (isbn, usuario, estado, fecha_devolucion, renovaciones)
            VALUES (%s, %s, 'ACTIVO', %s, 1)
            ON CONFLICT (isbn, usuario)
            DO UPDATE SET fecha_devolucion = EXCLUDED.fecha_devolucion,
                          renovaciones = LEAST(prestamos.renovaciones + 1, 2);
        """, (isbn, usuario, nueva_fecha))
    conn.commit()
    return {"status": "ok", "detalle": "renovacion completada"}


def aplicar_devolucion(conn, isbn, usuario):    
    try:
        with conn.cursor() as cur:
            # 1) marcar préstamo como DEVUELTO; si no existe, lo creamos DEVUELTO
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

            # 2) incrementar ejemplares del libro (UPSERT)
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
        
    Returns:
        Dict con status/error y detalles del préstamo
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1) Verificar que el libro existe y tiene ejemplares disponibles
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
            
            # 2) Verificar que el usuario no tenga ya un préstamo activo de este libro
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
            
            # 3) Calcular fecha de devolución (14 días desde hoy)
            fecha_prestamo = datetime.now()
            fecha_devolucion = fecha_prestamo + timedelta(days=14)
            
            # 4) Crear o actualizar el préstamo
            cur.execute("""
                INSERT INTO prestamos (isbn, usuario, estado, fecha_devolucion, renovaciones)
                VALUES (%s, %s, 'ACTIVO', %s, 0)
                ON CONFLICT (isbn, usuario)
                DO UPDATE SET estado='ACTIVO', 
                              fecha_devolucion=%s,
                              renovaciones=0;
            """, (isbn, usuario, fecha_devolucion, fecha_devolucion))
            
            # 5) Decrementar ejemplares disponibles
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


# ===== ZMQ REP Server =====
def main():
    # ZMQ
    context = zmq.Context()
    socket_rep = context.socket(zmq.REP)
    socket_rep.bind("tcp://*:5570")

    print("[GestorAlmacenamiento] Escuchando en 5570 (REP) - Postgres enabled")  

    # Conexión y esquema
    conn = connect_db()
    print("[GestorAlmacenamiento] Conectado a PostgreSQL")
    ensure_schema(conn)
    print("[GestorAlmacenamiento] Esquema de base de datos verificado")
    print("[GestorAlmacenamiento] Listo para recibir peticiones...")

    while True:
        try:
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

            else:
                resp = {"error": "accion_desconocida"}

            socket_rep.send_json(resp)

        except KeyboardInterrupt:
            break
        except Exception as e:
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
