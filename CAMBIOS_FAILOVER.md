# Cambios para Failover Automático al Puerto 5433

## Resumen
Se modificó el código para que el `gestor_almacenamiento` intente automáticamente conectar al puerto 5433 si falla en el puerto 5432.

---

## Archivos Modificados

### 1. `gestor_almacenamiento/gestor_a.py`

**Cambios realizados:**

#### a) Variables globales actualizadas (líneas 7-17)
- ✅ Cambiado `DB_STANDBY_HOST` default de `"postgres_standby"` a `"postgres_replica"`
- ✅ Agregada variable `current_db_port` para rastrear el puerto actual

```python
DB_STANDBY_HOST = os.getenv("DB_STANDBY_HOST", "postgres_replica")  # Cambiado
current_db_host = DB_HOST
current_db_port = DB_PORT  # Nueva variable
```

#### b) Función `connect_db_with_failover()` mejorada (líneas 33-98)
- ✅ Ahora prueba no solo diferentes hosts, sino también diferentes puertos (5432 y 5433)
- ✅ Orden de intentos:
  1. `current_db_host:current_db_port` (ej: postgres_primary:5432)
  2. `current_db_host:puerto_alternativo` (ej: postgres_primary:5433)
  3. `alternate_host:5432` (ej: postgres_replica:5432)
  4. `alternate_host:5433` (ej: postgres_replica:5433)
  5. Todas las combinaciones de hosts [postgres_primary, postgres_replica] × puertos [5432, 5433]

```python
# Lista de (host, puerto) para probar
hosts_to_try = []

# Intentar primero el host y puerto actuales
hosts_to_try.append((current_db_host, current_db_port))

# Luego intentar el host actual con el puerto alternativo
alt_port = 5433 if current_db_port == 5432 else 5432
hosts_to_try.append((current_db_host, alt_port))

# Luego intentar el host alternativo con ambos puertos
alternate_host = DB_STANDBY_HOST if current_db_host == DB_HOST else DB_HOST
hosts_to_try.append((alternate_host, 5432))
hosts_to_try.append((alternate_host, 5433))

# Asegurar todas las combinaciones
for host in [DB_HOST, DB_STANDBY_HOST]:
    for port in [5432, 5433]:
        if (host, port) not in hosts_to_try:
            hosts_to_try.append((host, port))
```

#### c) Logs mejorados
- ✅ Ahora muestran tanto host como puerto en todos los mensajes
- Ejemplo: `[DB] Intentando conectar a postgres_replica:5433...`
- Ejemplo: `[DB] ✅ FAILOVER: Cambiando de postgres_primary:5432 a postgres_replica:5433`

---

### 2. `docker-compose.yml`

**Cambios realizados:**

#### Agregada variable de entorno `DB_STANDBY_HOST` (línea 66)

```yaml
environment:
  DB_HOST: postgres_primary
  DB_STANDBY_HOST: postgres_replica  # Para failover automático al puerto 5433
  DB_PORT: 5432
  DB_NAME: library
  DB_USER: app
  DB_PASS: app
```

---

## Flujo de Failover Automático

### Escenario: Primary (5432) cae → Replica (5433) promovida

1. **Estado inicial**:
   - `postgres_primary:5432` (corriendo)
   - `postgres_replica:5433` (corriendo como réplica)
   - `gestor_almacenamiento` conectado a `postgres_primary:5432`

2. **Evento: Primary cae**:
   - `postgres_primary` detenido
   - `postgres_replica` promovida a primario (aún en puerto 5433)

3. **Reconexión automática del gestor**:
   - Conexión a `postgres_primary:5432` falla
   - Intenta `postgres_primary:5433` → falla (contenedor detenido)
   - Intenta `postgres_replica:5432` → falla (no escucha en 5432)
   - ✅ **Intenta `postgres_replica:5433` → ÉXITO!**
   - Log: `[DB] ✅ FAILOVER: Cambiando de postgres_primary:5432 a postgres_replica:5433`

4. **Estado final**:
   - `gestor_almacenamiento` ahora conectado a `postgres_replica:5433`
   - Sistema operacional nuevamente

---

## Prueba de Funcionamiento

### Paso 1: Reconstruir el gestor con los cambios

```powershell
# Detener el gestor actual
docker stop gestor_almacenamiento
docker rm gestor_almacenamiento

# Reconstruir con los cambios
docker-compose build gestor_almacenamiento

# Levantar de nuevo
docker-compose up -d gestor_almacenamiento
```

### Paso 2: Verificar logs iniciales

```powershell
docker logs gestor_almacenamiento --tail 20
```

**Resultado esperado**: 
```
[DB] Intentando conectar a postgres_primary:5432...
[DB] ✅ Conectado a postgres_primary:5432
```

### Paso 3: Simular failover

```powershell
# Detener primario
docker stop postgres_primary

# Promover réplica
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\failover-to-replica.ps1
```

### Paso 4: Probar operación

```powershell
# Esperar unos segundos para que el gestor reconecte
Start-Sleep -Seconds 10

# Intentar préstamo
python test_cliente.py prestamo 978-0596007126 usuario_test_failover
```

**Resultado esperado**: ✅ Operación exitosa

### Paso 5: Verificar logs del gestor

```powershell
docker logs gestor_almacenamiento --tail 30
```

**Logs esperados**:
```
[DB] ❌ Error conectando a postgres_primary:5432: ...
[DB] Intentando conectar a postgres_primary:5433...
[DB] ❌ Error conectando a postgres_primary:5433: ...
[DB] Intentando conectar a postgres_replica:5432...
[DB] ❌ Error conectando a postgres_replica:5432: ...
[DB] Intentando conectar a postgres_replica:5433...
[DB] ✅ FAILOVER: Cambiando de postgres_primary:5432 a postgres_replica:5433
```

---

## Ventajas de Esta Implementación

1. ✅ **Failover automático**: No requiere intervención manual después de ejecutar el script de promoción
2. ✅ **Multi-puerto**: Prueba automáticamente puertos 5432 y 5433
3. ✅ **Multi-host**: Prueba automáticamente hosts principal y alternativo
4. ✅ **Validación read-only**: Descarta conexiones a standbys (solo acepta primarios)
5. ✅ **Logs detallados**: Fácil de debuggear con logs de cada intento
6. ✅ **Sin cambios de arquitectura**: Funciona en el entorno Docker Compose existente

---

## Limitaciones Conocidas

1. **Tiempo de reconexión**: El gestor solo reconecta cuando intenta una operación (no es proactivo en background)
2. **Checkpoint manual**: Aún requieres ejecutar manualmente `failover-to-replica.ps1` para promover la réplica
3. **Puerto fijo de réplica**: Asume que la réplica siempre está en puerto 5433

---

## Para Producción

En un entorno de producción real, se recomendaría:

1. **Patroni** o **Repmgr**: Failover completamente automático
2. **PgBouncer** o **HAProxy**: Proxy que detecta automáticamente el primario
3. **Consul/etcd**: Service discovery para encontrar el primario actual
4. **Heartbeat monitoring**: Detectar fallos y activar failover sin intervención

Pero para un proyecto académico, esta solución es **ideal**: demuestra los conceptos sin sobrecomplej idad.

---

**Última actualización**: 2025-11-20 18:32:00
