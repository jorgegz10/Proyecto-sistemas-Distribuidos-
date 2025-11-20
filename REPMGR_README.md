# PostgreSQL Repmgr - Configuración de Failover Automático

## Descripción

Este proyecto implementa **failover automático** para PostgreSQL usando **repmgr** (Replication Manager). El sistema está compuesto por tres nodos:

- **postgres_primary**: Nodo primario que acepta escrituras
- **postgres_standby**: Nodo réplica que se promueve automáticamente a primario en caso de fallo
- **postgres_witness**: Nodo ligero que previene escenarios de split-brain

## Arquitectura

```
┌─────────────────────┐
│  postgres_primary   │ (Primary)
│  - Escrituras       │
│  - Puerto 5432      │
└──────────┬──────────┘
           │ Replicación streaming
           │
           v
┌─────────────────────┐         ┌─────────────────────┐
│  postgres_standby   │         │  postgres_witness   │
│  - Solo lectura*    │<------->│  - Quorum voting    │
│  - Puerto 5433      │         │  - Sin datos        │
│  - Failover auto    │         │  - Anti split-brain │
└─────────────────────┘         └─────────────────────┘

* Se promueve a primario (escritura) si el primario falla
```

## Características

✅ **Replicación Streaming**: Los datos se replican automáticamente de primario a standby  
✅ **Failover Automático**: Si el primario falla, el standby se promueve automáticamente en ~10-15 segundos  
✅ **Prevención de Split-Brain**: El nodo witness participa en la votación de quorum  
✅ **Reconexión Automática**: La aplicación detecta y reconecta al nuevo primario automáticamente  
✅ **Rejoin del Nodo Fallido**: El nodo recuperado puede reincorporarse como standby  
✅ **Switchover Manual**: Permite intercambio planificado de roles primario/standby  

## Archivos de Configuración

### Estructura de Carpetas

```
postgres-repmgr/
├── Dockerfile                  # Imagen personalizada con PostgreSQL 16 + repmgr
├── entrypoint.sh              # Script de inicialización para todos los nodos
└── repmgr.conf.template       # Template de configuración de repmgr
```

### Variables de Entorno

Cada nodo se configura mediante variables de entorno en docker-compose:

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `NODE_ID` | ID único del nodo (1, 2, 3) | `1` |
| `NODE_NAME` | Nombre del nodo | `postgres_primary` |
| `REPMGR_ROLE` | Rol del nodo | `primary`, `standby`, `witness` |
| `PRIMARY_HOST` | Hostname del primario | `postgres_primary` |
| `REPMGR_PASSWORD` | Contraseña del usuario repmgr | `repmgr` |
| `POSTGRES_DB` | Nombre de la base de datos | `library` |
| `POSTGRES_USER` | Usuario de la aplicación | `app` |
| `POSTGRES_PASSWORD` | Contraseña de la aplicación | `app` |

## Inicio Rápido

### 1. Limpiar volúmenes anteriores (importante)

```powershell
docker-compose -f docker-compose-postgres-only.yml down -v
```

### 2. Construir e iniciar el cluster

```powershell
# Solo PostgreSQL
docker-compose -f docker-compose-postgres-only.yml up --build

# O sistema completo
docker-compose up --build
```

### 3. Verificar estado del cluster

```powershell
docker exec postgres_primary repmgr cluster show
```

Deberías ver 3 nodos: 1 primary, 1 standby, 1 witness (todos running).

## Prueba de Failover

### Simular fallo del primario

```powershell
# Detener el primario
docker stop postgres_primary

# Esperar 15 segundos y verificar
Start-Sleep -Seconds 15
docker exec postgres_standby repmgr cluster show
```

El `postgres_standby` debe haberse promovido a **primary**.

### Verificar que el nuevo primario acepta escrituras

```powershell
docker exec postgres_standby psql -U app -d library -c "SELECT version();"
```

### Recuperar el nodo original

```powershell
# Reiniciar
docker start postgres_primary

# Esperar 30 segundos y verificar
Start-Sleep -Seconds 30
docker exec postgres_standby repmgr cluster show
```

El `postgres_primary` debe aparecer como **standby** siguiendo al nuevo primario.

## Reconexión de la Aplicación

El `gestor_almacenamiento` incluye lógica de failover automático:

1. **Detección de fallos**: Captura excepciones de conexión (`psycopg2.OperationalError`)
2. **Intento de reconexión**: Prueba conectar al host actual, luego al alternativo
3. **Verificación de escritura**: Asegura que la conexión sea de escritura (no read-only)
4. **Reconexión periódica**: Verifica la conexión cada 10 requests

Ver logs:
```powershell
docker logs gestor_almacenamiento
```

Deberías ver mensajes como:
```
[DB] ✅ FAILOVER: Cambiando de postgres_primary a postgres_standby
```

## Configuración de Repmgr

### Parámetros Importantes

- **`failover=automatic`**: Habilita failover automático
- **`monitor_interval_secs=2`**: Intervalo de verificación de salud (2 segundos)
- **`reconnect_attempts=6`**: Intentos de reconexión antes de declarar fallo
- **`primary_visibility_consensus=true`**: Requiere consenso para promover
- **`use_replication_slots=yes`**: Usa slots de replicación para prevenir pérdida de datos

### Comandos Útiles de Repmgr

```powershell
# Ver estado del cluster
docker exec <nodo> repmgr cluster show

# Ver eventos del cluster
docker exec <nodo> repmgr cluster event --all

# Verificar configuración de un nodo
docker exec <nodo> repmgr node check

# Ejecutar switchover manual
docker exec <standby> repmgr standby switchover

# Hacer rejoin manual (si es necesario)
docker exec <nodo> repmgr standby follow
```

## Troubleshooting

### El standby no replica datos

1. Verificar que el primario esté healthy:
   ```powershell
   docker ps
   ```

2. Ver logs del standby:
   ```powershell
   docker logs postgres_standby
   ```

3. Verificar conectividad:
   ```powershell
   docker exec postgres_standby pg_isready -h postgres_primary
   ```

### El failover no ocurre automáticamente

1. Verificar que `repmgrd` esté corriendo:
   ```powershell
   docker exec postgres_standby ps aux | grep repmgrd
   ```

2. Ver logs de repmgr:
   ```powershell
   docker exec postgres_standby cat /var/log/postgresql/repmgr.log
   ```

3. Verificar configuración:
   ```powershell
   docker exec postgres_standby cat /etc/repmgr.conf
   ```

### La aplicación no reconecta

1. Verificar variables de entorno:
   ```powershell
   docker exec gestor_almacenamiento env | grep DB_
   ```
   Debe incluir `DB_STANDBY_HOST=postgres_standby`

2. Ver logs de la aplicación:
   ```powershell
   docker logs gestor_almacenamiento
   ```

## Documentación Adicional

- **VERIFICACION_REPMGR.md**: Guía detallada de verificación paso a paso
- **Repmgr Official Docs**: https://www.repmgr.org/docs/current/
- **PostgreSQL Replication**: https://www.postgresql.org/docs/current/warm-standby.html

## Limitaciones y Consideraciones

- **Tiempo de failover**: ~10-15 segundos (configurable mediante `monitor_interval_secs`)
- **Pérdida de datos**: En failover automático puede haber pérdida mínima de transacciones no replicadas
- **Sincronía**: Por defecto usa replicación asíncrona (configurable a síncrona si se requiere)
- **Witness obligatorio**: Sin witness, un cluster de 2 nodos puede sufrir split-brain
- **Volúmenes persistentes**: Los datos persisten en volúmenes Docker incluso después de `docker-compose down`

## Recomendaciones de Producción

Si planeas usar esto en producción:

1. **Replicación síncrona**: Cambia `synchronous_commit` a `on` en `postgresql.conf`
2. **Monitoreo**: Implementa alertas para eventos de failover
3. **Backups**: Configura backups automáticos con `pg_basebackup` o herramientas como Barman
4. **Recursos**: Asigna CPU y memoria adecuadas a cada nodo
5. **Red**: Usa redes Docker personalizadas con DNS estable
6. **Seguridad**: Usa certificados SSL/TLS para conexiones de replicación
