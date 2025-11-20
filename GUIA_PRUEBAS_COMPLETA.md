# Guía Completa de Pruebas - Sistema Distribuido con Replicación PostgreSQL

Esta guía te llevará paso a paso desde cero hasta probar completamente el sistema con replicación y failover.

## Pre-requisitos

- Docker y Docker Compose instalados
- PowerShell (Windows)
- Puerto 5432, 5433, 5555, 5556, 5570, 8089 disponibles

---

## PARTE 1: Limpieza Total del Ambiente

### Paso 1.1: Detener todos los contenedores y limpiar volúmenes

```powershell
# Detener y eliminar todo
docker-compose down -v

# Limpiar contenedores huérfanos
docker-compose down --remove-orphans

# Verificar que no queden contenedores corriendo
docker ps -a
```

**Resultado esperado**: No debe haber contenedores del proyecto corriendo.

---

## PARTE 2: Levantar el Sistema Completo

### Paso 2.1: Construir e iniciar todos los servicios

```powershell
# Construir imágenes y levantar servicios
docker-compose up --build -d

# Ver el estado de los contenedores
docker ps
```

**Resultado esperado**: Deberías ver aproximadamente 10-12 contenedores corriendo:
- `postgres_primary` - BD primaria
- `postgres_replica` - BD réplica  
- `gestor_carga` - Balanceador de carga
- `gestor_almacenamiento` - Gestor de BD
- `actor_prestamo` - Actor de préstamos
- `actor_devolucion` - Actor de devoluciones
- `actor_renovacion` - Actor de renovaciones
- `proceso_solicitante` - Generador de solicitudes
- `run_renovaciones` - Procesador de renovaciones
- `locust_web` - Interfaz web de pruebas
- Otros servicios auxiliares

### Paso 2.2: Verificar logs iniciales

```powershell
# Ver logs del primario
docker logs postgres_primary --tail 20

# Ver logs de la réplica
docker logs postgres_replica --tail 20

# Ver logs del gestor de almacenamiento
docker logs gestor_almacenamiento --tail 20
```

**Resultado esperado**: 
- PostgreSQL debe mostrar "database system is ready to accept connections"
- Gestor de almacenamiento debe mostrar "Conectado a PostgreSQL (postgres_primary)"

---

## PARTE 3: Pruebas de Operaciones Básicas en la BD

### Paso 3.1: Verificar que las tablas existen

```powershell
# Listar tablas
docker exec postgres_primary psql -U app -d library -c "\dt"
```

**Resultado esperado**: Deberías ver las tablas `libros` y `prestamos`.

### Paso 3.2: Consultar libros existentes

```powershell
# Ver todos los libros
docker exec postgres_primary psql -U app -d library -c "SELECT * FROM libros;"
```

**Resultado esperado**: 4 libros de prueba con ISBNs como `978-0134685991`, etc.

### Paso 3.3: Insertar un nuevo libro

```powershell
# Insertar libro de prueba
docker exec postgres_primary psql -U app -d library -c "INSERT INTO libros (isbn, ejemplares) VALUES ('TEST-MANUAL-001', 10);"

# Verificar que se insertó
docker exec postgres_primary psql -U app -d library -c "SELECT * FROM libros WHERE isbn='TEST-MANUAL-001';"
```

**Resultado esperado**: El libro `TEST-MANUAL-001` con 10 ejemplares debe aparecer.

### Paso 3.4: Crear un préstamo

```powershell
# Insertar un préstamo
docker exec postgres_primary psql -U app -d library -c "INSERT INTO prestamos (isbn, usuario, estado, fecha_devolucion, renovaciones) VALUES ('TEST-MANUAL-001', 'usuario123', 'ACTIVO', NOW() + INTERVAL '14 days', 0);"

# Verificar el préstamo
docker exec postgres_primary psql -U app -d library -c "SELECT * FROM prestamos WHERE usuario='usuario123';"
```

**Resultado esperado**: El préstamo debe aparecer con estado `ACTIVO`.

### Paso 3.5: Actualizar ejemplares disponibles

```powershell
# Decrementar ejemplares (simular préstamo)
docker exec postgres_primary psql -U app -d library -c "UPDATE libros SET ejemplares = ejemplares - 1 WHERE isbn='TEST-MANUAL-001';"

# Verificar el cambio
docker exec postgres_primary psql -U app -d library -c "SELECT * FROM libros WHERE isbn='TEST-MANUAL-001';"
```

**Resultado esperado**: Los ejemplares ahora deben ser 9.

---

## PARTE 4: Verificación de Replicación

### Paso 4.1: Verificar estado de replicación

```powershell
# Ver conexiones de replicación activas
docker exec postgres_primary psql -U app -d library -c "SELECT * FROM pg_stat_replication;"
```

**Resultado esperado**: Debe mostrar 1 fila con:
- `usename`: `replicator`
- `application_name`: `postgres_replica`
- `state`: `streaming`

### Paso 4.2: Insertar datos en el primario

```powershell
# Insertar libro de prueba de replicación
docker exec postgres_primary psql -U app -d library -c "INSERT INTO libros (isbn, ejemplares) VALUES ('REPL-TEST-001', 15);"

# Confirmar en primario
docker exec postgres_primary psql -U app -d library -c "SELECT * FROM libros WHERE isbn='REPL-TEST-001';"
```

**Resultado esperado**: El libro aparece en el primario.

### Paso 4.3: Verificar en la réplica (CLAVE)

```powershell
# Esperar 2-3 segundos para que replique
Start-Sleep -Seconds 3

# Consultar en la réplica
docker exec postgres_replica psql -U app -d library -c "SELECT * FROM libros WHERE isbn='REPL-TEST-001';"
```

**Resultado esperado**: ✅ **El mismo libro debe aparecer en la réplica** con 15 ejemplares.

### Paso 4.4: Verificar lag de replicación

```powershell
# Verificar el retraso de replicación
docker exec postgres_replica psql -U app -d library -c "SELECT NOW() - pg_last_xact_replay_timestamp() AS replication_lag;"
```

**Resultado esperado**: El lag debe ser muy pequeño (< 00:00:01).

### Paso 4.5: Intentar escribir en la réplica (debe fallar)

```powershell
# Intentar INSERT en réplica (debe fallar)
docker exec postgres_replica psql -U app -d library -c "INSERT INTO libros (isbn, ejemplares) VALUES ('FAIL-TEST', 1);"
```

**Resultado esperado**: ❌ Error: `ERROR: cannot execute INSERT in a read-only transaction`

Esto confirma que la réplica está en modo **solo lectura**.

---

## PARTE 5: Prueba de Failover Manual

### Paso 5.1: Verificar que ambos nodos están corriendo

```powershell
# Ver contenedores
docker ps | Select-String "postgres"
```

**Resultado esperado**: Ambos `postgres_primary` y `postgres_replica` deben estar UP.

### Paso 5.2: Simular fallo del primario

```powershell
# Detener el primario (simula un fallo)
docker stop postgres_primary

# Confirmar que se detuvo
docker ps | Select-String "postgres_primary"
```

**Resultado esperado**: `postgres_primary` no debe aparecer en la lista.

### Paso 5.3: Ejecutar script de failover automático

```powershell
# Ejecutar el script de failover
.\failover-to-replica.ps1
```

**Resultado esperado**: El script debe mostrar:
- ✅ postgres_replica está corriendo
- ✅ La réplica fue promovida exitosamente
- ✅ Inserción exitosa - El nuevo primario acepta escrituras

### Paso 5.4: Verificar que la réplica acepta escrituras

```powershell
# Insertar datos en el nuevo primario (ex-réplica)
docker exec postgres_replica psql -U app -d library -c "INSERT INTO libros (isbn, ejemplares) VALUES ('POST-FAILOVER-001', 20);"

# Verificar el dato
docker exec postgres_replica psql -U app -d library -c "SELECT * FROM libros WHERE isbn='POST-FAILOVER-001';"
```

**Resultado esperado**: ✅ El INSERT funciona correctamente. La réplica ahora es primario.

### Paso 5.5: Verificar que NO está en modo recovery

```powershell
# Verificar estado (debe ser 'f' = false, NO en recovery)
docker exec postgres_replica psql -U app -d library -c "SELECT pg_is_in_recovery();"
```

**Resultado esperado**: Debe mostrar `f` (false), indicando que ya NO es réplica.

---

## PARTE 6: Verificar Reconexión de la Aplicación

### Paso 6.1: Ver logs del gestor de almacenamiento

```powershell
# Ver logs recientes
docker logs gestor_almacenamiento --tail 30
```

**Resultado esperado**: Deberías ver intentos de reconexión como:
```
[DB] ⚠️  Conexión perdida...
[DB] Intentando conectar a postgres_primary:5432...
[DB] ❌ Error conectando a postgres_primary...
[DB] Intentando conectar a postgres_standby:5432...
```

> **Nota**: En el docker-compose.yml actual, los servicios apuntan a `postgres_primary`, no a `postgres_standby`. Para que la reconexión automática funcione completamente, necesitarías actualizar las variables de entorno o usar un proxy/balanceador.

---

## PARTE 7: Pruebas de la Aplicación Completa

### Paso 7.1: Verificar que los actores están corriendo

```powershell
# Ver logs de los actores
docker logs actor_prestamo --tail 10
docker logs actor_devolucion --tail 10
docker logs actor_renovacion --tail 10
```

**Resultado esperado**: Los actores deben estar escuchando y procesando mensajes.

### Paso 7.2: Abrir interfaz web de Locust

```powershell
# Abrir en el navegador
Start-Process "http://localhost:8089"
```

**Resultado esperado**: Deberías ver la interfaz web de Locust para pruebas de carga.

### Paso 7.3: Ver comunicación ZMQ

```powershell
# Ver logs del gestor de carga
docker logs gestor_carga --tail 20
```

**Resultado esperado**: Deberías ver actividad de enrutamiento de mensajes.

---

## PARTE 8: Recuperación y Limpieza

### Paso 8.1: Reiniciar el primario original (opcional)

```powershell
# Reiniciar el primario
docker start postgres_primary
```

> **Nota**: El primario original se levantará, pero como ya tiene datos antiguos, NO funcionará como réplica automáticamente. Necesitarías reconfigurarlo o limpiarlo.

### Paso 8.2: Detener todo el ambiente

```powershell
# Detener todos los servicios
docker-compose down

# Si quieres eliminar volúmenes también
docker-compose down -v
```

---

## Resumen de Comandos Rápidos

```powershell
# Levantar todo desde cero
docker-compose down -v
docker-compose up --build -d

# Verificar replicación
docker exec postgres_primary psql -U app -d library -c "INSERT INTO libros (isbn, ejemplares) VALUES ('TEST-$(Get-Date -Format yyyyMMddHHmmss)', 5);"
Start-Sleep -Seconds 2
docker exec postgres_replica psql -U app -d library -c "SELECT * FROM libros ORDER BY isbn DESC LIMIT 1;"

# Failover
docker stop postgres_primary
.\failover-to-replica.ps1

# Verificar nuevo primario
docker exec postgres_replica psql -U app -d library -c "SELECT pg_is_in_recovery();"
docker exec postgres_replica psql -U app -d library -c "INSERT INTO libros VALUES ('TEST-NEW', 1);"

# Limpiar todo
docker-compose down -v
```

---

## Troubleshooting

### Problema: "Port already allocated"
```powershell
# Ver qué está usando el puerto
netstat -ano | findstr :5432
netstat -ano | findstr :5433

# Detener el proceso o cambiar puertos en docker-compose.yml
```

### Problema: "relation does not exist"
```powershell
# Ejecutar manualmente el script de inicialización
docker exec postgres_primary psql -U app -d library -f /docker-entrypoint-initdb.d/01-init.sql
```

### Problema: Contenedores no inician
```powershell
# Ver logs de un contenedor específico
docker logs <nombre_contenedor>

# Reconstruir desde cero
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

---

## Checklist de Verificación Final

- [ ] ✅ Todos los contenedores están corriendo
- [ ] ✅ Puedo insertar datos en `postgres_primary`
- [ ] ✅ Los datos se replican a `postgres_replica` en < 3 segundos
- [ ] ✅ La réplica NO acepta escrituras (es read-only)
- [ ] ✅ Al detener el primario, puedo ejecutar el failover
- [ ] ✅ Después del failover, la ex-réplica acepta escrituras
- [ ] ✅ Los actores procesan mensajes correctamente
- [ ] ✅ La interfaz de Locust está accesible

Si todos los checks están ✅, ¡tu sistema está funcionando perfectamente!
