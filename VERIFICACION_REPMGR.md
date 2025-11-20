# Guía de Verificación - Failover Automático con Repmgr

## Requisitos Previos

Antes de comenzar, asegúrate de que los volúmenes anteriores están limpios:

```powershell
# Detener todos los contenedores y eliminar volúmenes
docker-compose down -v

# O si usas docker-compose-postgres-only.yml
docker-compose -f docker-compose-postgres-only.yml down -v
```

## Paso 1: Construir e Iniciar el Cluster

```powershell
# Opción A: Solo PostgreSQL (recomendado para pruebas iniciales)
docker-compose -f docker-compose-postgres-only.yml up --build

# Opción B: Sistema completo
docker-compose up --build
```

**Salida esperada:**
- `postgres_primary` debe inicializar primero
- `postgres_standby` debe clonar datos del primario
- `postgres_witness` debe registrarse exitosamente
- Verás logs como: `✅ Conectado a postgres_primary`

## Paso 2: Verificar Estado del Cluster

```powershell
# Ver el estado actual del cluster
docker exec postgres_primary repmgr cluster show
```

**Salida esperada:**
```
 ID | Name              | Role    | Status    | Upstream         | Location | Priority | Timeline | Connection string
----+-------------------+---------+-----------+------------------+----------+----------+----------+-------
 1  | postgres_primary  | primary | * running |                  | default  | 100      | 1        | host=postgres_primary ...
 2  | postgres_standby  | standby |   running | postgres_primary | default  | 100      | 1        | host=postgres_standby ...
 3  | postgres_witness  | witness | * running | postgres_primary | default  | 0        |          | host=postgres_witness ...
```

## Paso 3: Verificar Replicación de Datos

```powershell
# 1. Insertar un libro de prueba en el primario
docker exec postgres_primary psql -U app -d library -c "INSERT INTO books (isbn, title, author, copies_available, total_copies) VALUES ('REPMGR-TEST-001', 'Repmgr Test Book', 'Test Author', 5, 5);"

# 2. Esperar 2-3 segundos para que replique
Start-Sleep -Seconds 3

# 3. Verificar en el standby
docker exec postgres_standby psql -U app -d library -c "SELECT * FROM books WHERE isbn='REPMGR-TEST-001';"
```

**Salida esperada:** Deberías ver el libro en ambos nodos.

## Paso 4: Simular Fallo del Primario

```powershell
# Detener el primario abruptamente
docker stop postgres_primary

# Ver logs del standby para ver el failover
docker logs -f postgres_standby
```

**Salida esperada:**
- Después de ~10-15 segundos, verás mensajes de promoción
- El daemon repmgrd detecta el fallo
- El standby se promueve a primario automáticamente

## Paso 5: Verificar Promoción

```powershell
# Verificar que el standby ahora es primario
docker exec postgres_standby repmgr cluster show
```

**Salida esperada:**
```
 ID | Name              | Role    | Status      | Upstream | Location | Priority | Timeline | Connection string
----+-------------------+---------+-------------+----------+----------+----------+----------+-------
 1  | postgres_primary  | primary | - failed    |          | default  | 100      | 1        | host=postgres_primary ...
 2  | postgres_standby  | primary | * running   |          | default  | 100      | 2        | host=postgres_standby ...
 3  | postgres_witness  | witness | * running   | postgres_standby | default  | 0  |          | host=postgres_witness ...
```

Nota: `postgres_standby` ahora tiene el rol **primary**.

## Paso 6: Verificar Escritura en el Nuevo Primario

```powershell
# Insertar otro libro en el nuevo primario
docker exec postgres_standby psql -U app -d library -c "INSERT INTO books (isbn, title, author, copies_available, total_copies) VALUES ('AFTER-FAILOVER-001', 'After Failover Book', 'Failover Author', 3, 3);"

# Verificar que se insertó
docker exec postgres_standby psql -U app -d library -c "SELECT * FROM books WHERE isbn='AFTER-FAILOVER-001';"
```

**Salida esperada:** El libro se inserta correctamente en el nuevo primario.

## Paso 7: Verificar Reconexión de la Aplicación

Si iniciaste el sistema completo, verifica los logs del gestor de almacenamiento:

```powershell
docker logs gestor_almacenamiento --tail 50
```

**Salida esperada:**
```
[DB] ⚠️  Conexión perdida...
[DB] Intentando conectar a postgres_standby:5432...
[DB] ✅ FAILOVER: Cambiando de postgres_primary a postgres_standby
[DB] ✅ Conectado a postgres_standby
```

## Paso 8: Recuperar el Nodo Original (Rejoin)

```powershell
# 1. Reiniciar el antiguo primario
docker start postgres_primary

# 2. Esperar a que arranque (30-60 segundos)
Start-Sleep -Seconds 30

# 3. Ver logs para confirmar que se unió como standby
docker logs postgres_primary --tail 50

# 4. Verificar cluster
docker exec postgres_standby repmgr cluster show
```

**Salida esperada:**
- `postgres_primary` debe aparecer como **standby**
- Estará siguiendo a `postgres_standby` (el nuevo primario)

## Paso 9: Switchover Manual (Opcional)

Si quieres devolver `postgres_primary` a su rol original:

```powershell
# Ejecutar switchover desde el antiguo primario (ahora standby)
docker exec postgres_primary repmgr standby switchover --siblings-follow

# Verificar cluster nuevamente
docker exec postgres_primary repmgr cluster show
```

**Salida esperada:**
- `postgres_primary` vuelve a ser **primary**
- `postgres_standby` vuelve a ser **standby**

## Métricas de Éxito

✅ **Cluster inicializado correctamente** (3 nodos registrados)  
✅ **Replicación funcionando** (datos aparecen en standby < 3 segundos)  
✅ **Failover automático** (ocurre en < 15 segundos después del fallo)  
✅ **Nuevo primario acepta escrituras** (inserts exitosos)  
✅ **Aplicación reconecta automáticamente** (sin intervención manual)  
✅ **Nodo original puede hacer rejoin** (vuelve como standby)  
✅ **Switchover manual funciona** (intercambio de roles planificado)

## Troubleshooting

### El standby no clona datos del primario
- Verifica que `postgres_primary` esté healthy: `docker ps`
- Revisa logs del standby: `docker logs postgres_standby`
- Asegúrate de haber eliminado volúmenes anteriores: `docker-compose down -v`

### El failover no ocurre automáticamente
- Verifica que `repmgrd` esté corriendo: `docker exec postgres_standby ps aux | grep repmgr`
- Revisa configuración: `docker exec postgres_standby cat /etc/repmgr.conf`
- Espera al menos 15-20 segundos después de detener el primario

### La aplicación no reconecta
- Verifica variables de entorno: `docker exec gestor_almacenamiento env | grep DB_`
- Debe incluir `DB_STANDBY_HOST=postgres_standby`
- Revisa logs: `docker logs gestor_almacenamiento`

### Split-brain detectado
- El witness debe estar corriendo: `docker ps | grep witness`
- Si fallan 2 nodos simultáneamente, el witness previene promoción automática

## Comandos Útiles

```powershell
# Ver todos los eventos de repmgr
docker exec postgres_standby repmgr cluster event --all

# Ver solo eventos recientes
docker exec postgres_standby repmgr cluster event --limit 20

# Ver configuración de un nodo
docker exec postgres_primary cat /etc/repmgr.conf

# Ver logs de repmgr
docker exec postgres_standby cat /var/log/postgresql/repmgr.log

# Estado de replicación
docker exec postgres_standby psql -U repmgr -d repmgr -c "SELECT * FROM repmgr.nodes;"
```
