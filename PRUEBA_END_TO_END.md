# Prueba End-to-End: Sistema Distribuido con Mensajería ZMQ y Failover de BD

Esta guía demuestra el sistema completo usando la mensajería ZMQ entre gestores, actores y la base de datos, culminando con un failover manual.

---

## Arquitectura del Sistema

```
[Cliente] --ZMQ REQ/REP--> [Gestor Carga:5555]
                                    |
                                    +--ZMQ PUB/SUB--> [Actores]
                                    |                  - actor_prestamo
                                    |                  - actor_devolucion
                                    |                  - actor_renovacion
                                    |
                                    +--ZMQ REQ/REP--> [Gestor Almacenamiento:5570]
                                                              |
                                                              v
                                                      [PostgreSQL Primary]
                                                              |
                                                        (Replicación)
                                                              v
                                                      [PostgreSQL Replica]
```

---

## PARTE 1: Pre

paración del Sistema

### Paso 1.1: Limpiar ambiente

```powershell
docker-compose down -v
docker ps -a  # Verificar que no queden contenedores
```

### Paso 1.2: Levantar todos los servicios

```powershell
# Construir y levantar
docker-compose up --build -d

# Esperar a que inicien (60 segundos)
Start-Sleep -Seconds 60

# Verificar contenedores
docker ps --format "table {{.Names}}\t{{.Status}}"
```

**Resultado esperado**: Ver todos los contenedores corriendo (~10-12):
- `gestor_carga`, `gestor_almacenamiento`
- `postgres_primary`, `postgres_replica`
- `actor_prestamo`, `actor_devolucion`, `actor_renovacion`
- `proceso_solicitante`, `locust_web`

### Paso 1.3: Verificar conectividad de gestores

```powershell
# Ver logs del gestor de almacenamiento
docker logs gestor_almacenamiento --tail 20

# Ver logs del gestor de carga
docker logs gestor_carga --tail 20
```

**Resultado esperado**: 
- `Gestor listo en puertos 5555 (REQ/REP) y 5556 (PUB/SUB)`
- `Conectado a PostgreSQL (postgres_primary)`

---

## PARTE 2: Operaciones CRUD a través del Sistema de Mensajería

### Paso 2.1: Crear script de cliente Python para enviar mensajes

Crea un archivo `test_cliente.py` en el directorio raíz:

```python
import zmq
import json
import sys

def enviar_peticion(socket, operacion, isbn, usuario="test_user"):
    mensaje = {
        "operacion": operacion,
        "isbn": isbn,
        "usuario": usuario
    }
    print(f"\n📤 Enviando: {mensaje}")
    socket.send_json(mensaje)
    
    respuesta = socket.recv_json()
    print(f"📥 Respuesta: {json.dumps(respuesta, indent=2)}")
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
```

### Paso 2.2: Verificar libros existentes (READ)

```powershell
# Ver libros en la BD directamente (para referencia)
docker exec postgres_primary psql -U app -d library -c "SELECT isbn, ejemplares FROM libros;"
```

**Resultado esperado**: 4 libros iniciales (978-0134685991, 978-0135957059, 978-0596007126, 978-1491950357)

### Paso 2.3: Consultar disponibilidad de un libro (operación consulta)

```powershell
# Consultar libro a través del sistema de mensajería
python test_cliente.py consulta 978-0134685991
```

**Resultado esperado**: Respuesta JSON del gestor confirmando la consulta

### Paso 2.4: Realizar préstamo (CREATE - flujo completo)

```powershell
# Solicitar préstamo de un libro
python test_cliente.py prestamo 978-0134685991 usuario_test_1
```

**Flujo que ocurre internamente**:
1. Cliente envía petición ZMQ REQ/REP a `gestor_carga:5555`
2. Gestor Carga valida el libro con `gestor_almacenamiento:5570` (ZMQ síncronoPUB:5556)`
3. `actor_prestamo` procesa el préstamo (subscribe al topic "prestamo")
4. Actor registra el préstamo en la BD y decrementa ejemplares

**Verificar en la BD**:

```powershell
# Ver préstamo creado
docker exec postgres_primary psql -U app -d library -c "SELECT * FROM prestamos WHERE usuario='usuario_test_1';"

# Ver ejemplares decrementados
docker exec postgres_primary psql -U app -d library -c "SELECT isbn, ejemplares FROM libros WHERE isbn='978-0134685991';"
```

**Resultado esperado**: 
- Préstamo con estado `ACTIVO`
- Ejemplares decrementados en 1

### Paso 2.5: Verificar replicación a réplica (READ)

```powershell
# Esperar replicación
Start-Sleep -Seconds 3

# Ver el mismo préstamo en la réplica
docker exec postgres_replica psql -U app -d library -c "SELECT * FROM prestamos WHERE usuario='usuario_test_1';"
```

**Resultado esperado**: ✅ El préstamo debe aparecer en la réplica

### Paso 2.6: Renovar préstamo (UPDATE)

```powershell
# Renovar el préstamo
python test_cliente.py renovacion 978-0134685991 usuario_test_1
```

**Flujo interno**:
1. Cliente → Gestor Carga (REQ/REP síncronoén)
2. Gestor Carga → Gestor Almacenamiento (REQ/REP)
3. Gestor Almacenamiento actualiza `renovaciones` y `fecha_devolucion`
4. Respuesta síncrona hasta el cliente

**Verificar renovación**:

```powershell
docker exec postgres_primary psql -U app -d library -c "SELECT usuario, renovaciones, fecha_devolucion FROM prestamos WHERE isbn='978-0134685991';"
```

**Resultado esperado**: Campo `renovaciones` incrementado a 1

### Paso 2.7: Intentar segunda renovación

```powershell
# Renovar otra vez
python test_cliente.py renovacion 978-0134685991 usuario_test_1
```

**Resultado esperado**: `renovaciones` ahora es 2

### Paso 2.8: Intentar tercera renovación (debe fallar)

```powershell
# Intentar tercera renovación
python test_cliente.py renovacion 978-0134685991 usuario_test_1
```

**Resultado esperado**: Error `LimiteRenovaciones` - máximo 2 renovaciones permitidas

### Paso 2.9: Devolver libro (DELETE conceptual)

```powershell
# Devolver libro
python test_cliente.py devolucion 978-0134685991 usuario_test_1
```

**Flujo interno**:
1. Cliente → Gestor Carga
2. Gestor Carga → PUB topic "devolucion"
3. `actor_devolucion` procesa (SUB)
4. Actor actualiza estado a `DEVUELTO` e incrementa ejemplares

**Verificar devolución**:

```powershell
# Ver préstamo marcado como DEVUELTO
docker exec postgres_primary psql -U app -d library -c "SELECT usuario, estado FROM prestamos WHERE isbn='978-0134685991';"

# Ver ejemplares restaurados
docker exec postgres_primary psql -U app -d library -c "SELECT isbn, ejemplares FROM libros WHERE isbn='978-0134685991';"
```

**Resultado esperado**:
- Estado del préstamo: `DEVUELTO`
- Ejemplares incrementados en 1

---

## PARTE 3: Monitoreo del Sistema en Tiempo Real

### Paso 3.1: Ver logs de actores procesando mensajes

```powershell
# En una terminal separada, seguir logs del actor de préstamos
docker logs actor_prestamo --follow

# En otra terminal, logs del actor de devoluciones
docker logs actor_devolucion --follow
```

### Paso 3.2: Monitorear replicación

```powershell
# Ver estado de replicación
docker exec postgres_primary psql -U app -d library -c "SELECT application_name, state, sync_state, write_lag, replay_lag FROM pg_stat_replication;"
```

**Resultado esperado**: `postgres_replica` en estado `streaming` con lag mínimo

### Paso 3.3: Verificar lag de replicación

```powershell
docker exec postgres_replica psql -U app -d library -c "SELECT NOW() - pg_last_xact_replay_timestamp() AS replication_lag;"
```

**Resultado esperado**: Lag < 3 segundos

---

## PARTE 4: Prueba de Carga con múltiples operaciones

### Paso 4.1: Crear préstamos masivos

Crea `test_masivo.py`:

```python
import zmq
import time

def enviar_prestamo(socket, isbn, usuario):
    mensaje = {"operacion": "prestamo", "isbn": isbn, "usuario": usuario}
    socket.send_json(mensaje)
    return socket.recv_json()

def main():
    context = zmq.Context()
    isbns = ["978-0134685991", "978-0135957059", "978-0596007126", "978-1491950357"]
    
    for i in range(10):
        socket = context.socket(zmq.REQ)
        socket.connect("tcp://localhost:5555")
        
        isbn = isbns[i % len(isbns)]
        usuario = f"usuario_carga_{i}"
        
        print(f"Préstamo {i+1}: {isbn} para {usuario}")
        resp = enviar_prestamo(socket, isbn, usuario)
        print(f"  → {resp.get('mensaje', 'OK')}")
        
        socket.close()
        time.sleep(0.5)
    
    context.term()

if __name__ == "__main__":
    main()
```

```powershell
python test_masivo.py
```

### Paso 4.2: Verificar préstamos creados

```powershell
docker exec postgres_primary psql -U app -d library -c "SELECT COUNT(*) FROM prestamos WHERE usuario LIKE 'usuario_carga_%';"
```

**Resultado esperado**: 10 préstamos creados

### Paso 4.3: Verificar en réplica

```powershell
Start-Sleep -Seconds 5
docker exec postgres_replica psql -U app -d library -c "SELECT COUNT(*) FROM prestamos WHERE usuario LIKE 'usuario_carga_%';"
```

**Resultado esperado**: Los mismos 10 préstamos replicados

---

## PARTE 5: Simulación de Fallo y Failover

### Paso 5.1: Snapshot del estado

```powershell
# Contar registros antes del failover
$libros_antes = (docker exec postgres_primary psql -U app -d library -tAc "SELECT COUNT(*) FROM libros;").Trim()
$prestamos_antes = (docker exec postgres_primary psql -U app -d library -tAc "SELECT COUNT(*) FROM prestamos;").Trim()

Write-Host "📊 ESTADO ANTES DEL FAILOVER:"
Write-Host "  - Libros: $libros_antes"
Write-Host "  - Préstamos: $prestamos_antes"
```

### Paso 5.2: Simular fallo del primario

```powershell
Write-Host "`n🔴 Simulando fallo del primario..."
docker stop postgres_primary

# Verificar contenedores
docker ps | Select-String "postgres"
```

**Resultado esperado**: Solo `postgres_replica` corriendo

### Paso 5.3: Intentar operación (debe fallar o tardar)

```powershell
# Esto probablemente falle o timeout
python test_cliente.py consulta 978-0134685991
```

**Resultado esperado**: Timeout o error de conexión (gestor_almacenamiento perdió conexión al primario)

### Paso 5.4: Ejecutar Failover

```powershell
# Habilitar ejecución de scripts
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Ejecutar failover
.\failover-to-replica.ps1
```

**Resultado esperado**:
```
✅ postgres_replica está corriendo
waiting for server to promote.... done
server promoted
✅ La réplica fue promovida exitosamente a primario
✅ Inserción exitosa
✅ Failover completado!
```

### Paso 5.5: Verificar nuevo primario

```powershell
# Verificar que NO está en recovery
docker exec postgres_replica psql -U app -d library -c "SELECT pg_is_in_recovery();"
```

**Resultado esperado**: `f` (false) - Es primario ahora

### Paso 5.6: Verificar datos preservados

```powershell
$libros_despues = (docker exec postgres_replica psql -U app -d library -tAc "SELECT COUNT(*) FROM libros;").Trim()
$prestamos_despues = (docker exec postgres_replica psql -U app -d library -tAc "SELECT COUNT(*) FROM prestamos;").Trim()

Write-Host "`n📊 ESTADO DESPUÉS DEL FAILOVER:"
Write-Host "  - Libros: $libros_despues (antes: $libros_antes)"
Write-Host "  - Préstamos: $prestamos_despues (antes: $prestamos_antes)"

if ($libros_despues -eq $libros_antes -and $prestamos_despues -eq $prestamos_antes) {
    Write-Host "✅ TODOS LOS DATOS PRESERVADOS" -ForegroundColor Green
} else {
    Write-Host "❌ PÉRDIDA DE DATOS DETECTADA" -ForegroundColor Red
}
```

---

## PARTE 6: Reconexión del Gestor de Almacenamiento

### Paso 6.1: Actualizar variable de entorno (manual)

El `gestor_almacenamiento` actualmente conecta a `postgres_primary:5432`. Para que use el nuevo primario:

**Opción 1**: Reiniciar gestor apuntando a postgres_replica

```powershell
docker stop gestor_almacenamiento
docker rm gestor_almacenamiento

# Editarcompose.yml temporalmente cambiar DB_HOST a postgres_replica
# Luego:
docker-compose up -d gestor_almacenamiento
```

**Opción 2**: El gestor tiene lógica de failover automático

```powershell
# Ver si hay intentos de reconexión
docker logs gestor_almacenamiento --tail 50
```

Buscar mensajes como:
- `[DB] ❌ Error conectando a postgres_primary`
- `[DB] Intentando conectar a postgres_standby`
- `[DB] ✅ FAILOVER: Cambiando de postgres_primary a postgres_standby`

### Paso 6.2: Probar operación después del failover

Una vez que el gestor esté reconectado:

```powershell
# Intentar nuevo préstamo
python test_cliente.py prestamo 978-0596007126 usuario_post_failover
```

**Resultado esperado**: ✅ El préstamo funciona correctamente

### Paso 6.3: Verificar en el nuevo primario

```powershell
docker exec postgres_replica psql -U app -d library -c "SELECT * FROM prestamos WHERE usuario='usuario_post_failover';"
```

**Resultado esperado**: Préstamo creado exitosamente en el nuevo primario

---

## PARTE 7: Resumen y Limpieza

### Resumen de lo demostrado

- ✅ **Mensajería ZMQ REQ/REP**: Cliente ↔ Gestor Carga
- ✅ **Mensajería ZMQ PUB/SUB**: Gestor Carga → Actores
- ✅ **CRUD completo**: Préstamo (CREATE), Consulta (READ), Renovación (UPDATE), Devolución (semantic DELETE)
- ✅ **Replicación streaming**: Primary → Replica (< 3 seg)
- ✅ **Failover manual**: Promoción de réplica a primario
- ✅ **Preservación de datos**: 100% de datos intactos post-failover
- ✅ **Sistema distribuido funcional**: Múltiples gestores y actores coordinados

### Métricas del sistema

```powershell
Write-Host "`n📈 MÉTRICAS FINALES:"
docker exec postgres_replica psql -U app -d library -tAc "SELECT COUNT(*) FROM libros;" | ForEach-Object { Write-Host "  - Total libros: $_" }
docker exec postgres_replica psql -U app -d library -tAc "SELECT COUNT(*) FROM prestamos WHERE estado='ACTIVO';" | ForEach-Object { Write-Host "  - Préstamos activos: $_" }
docker exec postgres_replica psql -U app -d library -tAc "SELECT COUNT(*) FROM prestamos WHERE estado='DEVUELTO';" | ForEach-Object { Write-Host "  - Préstamos devueltos: $_" }
```

### Limpieza

```powershell
# Detener todo
docker-compose down

# Si quieres eliminar volúmenes también
docker-compose down -v
```

---

## Checklist de Verificación

- [ ] ✅ Sistema completo levantado (gestores + actores + BD)
- [ ] ✅ Mensajería ZMQ REQ/REP funcionando
- [ ] ✅ Mensajería ZMQ PUB/SUB funcionando
- [ ] ✅ Préstamo creado vía mensajería (actor procesa)
- [ ] ✅ Consulta respondida por gestor
- [ ] ✅ Renovación procesada (máximo 2)
- [ ] ✅ Devolución procesada (estado actualizado)
- [ ] ✅ Replicación < 5 segundos
- [ ] ✅ Failover manual exitoso
- [ ] ✅ Datos preservados 100%
- [ ] ✅ Sistema funcional post-failover

---

## Troubleshooting

### Error: Connection timeout en test_cliente.py

```powershell
# Verificar que gestor_carga está corriendo
docker logs gestor_carga --tail 20

# Verificar puerto expuesto
docker port gestor_carga
```

### Error: Actor no procesa mensajes

```powershell
# Ver logs del actor
docker logs actor_prestamo --tail 50

# Verificar que está subscrito al topic correcto
docker exec actor_prestamo ps aux
```

### Error: Gestor almacenamiento no conecta

```powershell
# Ver logs
docker logs gestor_almacenamiento --tail 30

# Verificar conectividad a BD
docker exec gestor_almacenamiento ping postgres_primary -c 2
```

---

## Comandos de Referencia Rápida

```powershell
# Ver todos los contenedores
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Logs de un servicio
docker logs <nombre> --tail 50 --follow

# Ejecutar SQL en BD
docker exec postgres_primary psql -U app -d library -c "<SQL>"

# Enviar mensaje al gestor
python test_cliente.py <operacion> <isbn> [usuario]

# Failover
.\failover-to-replica.ps1
```

---

**Duración estimada de la prueba**: 25-30 minutos

Esta prueba demuestra un sistema distribuido real con mensajería asíncrona, persistencia con replicación y tolerancia a fallos mediante failover manual.
