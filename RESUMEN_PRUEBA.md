# Resumen de Prueba End-to-End Completada

## ✅ Pruebas Ejecutadas Exitosamente

### PARTE 2: Operaciones CRUD a través de Mensajería ZMQ

#### 2.3 Consulta (READ)
- ✅ Cliente envió mensaje ZMQ → Gestor Carga (puerto 5555)
- ✅ Respuesta exitosa: `"Consulta recibida"`

#### 2.4 Préstamo (CREATE)
- ✅ Cliente solicitó préstamo para ISBN `978-0134685991`, usuario `usuario_test_1`
- ✅ Gestor Carga validó libro y publicó evento PUB/SUB
- ✅ `actor_prestamo` procesó la solicitud
- ✅ Préstamo creado en BD con estado `ACTIVO`
- ✅ Ejemplares decrementados: 5 → 4

#### 2.5 Verificación de Replicación
- ✅ Préstamo replicado a `postgres_replica` en < 5 segundos

#### 2.6 Primera Renovación (UPDATE)
- ✅ Renovación procesada síncronamente
- ✅ Campo `renovaciones` actualizado: 0 → 1
- ✅ Fecha de devolución extendida +7 días

#### 2.7 Segunda Renovación
- ✅ Segunda renovación exitosa
- ✅ `renovaciones`: 1 → 2

#### 2.8 Tercera Renovación (validación de límite)
- ✅ Sistema rechazó correctamente con error: `LimiteRenovaciones`
- ✅ Mensaje: "Se alcanzó el límite de 2 renovaciones (actual: 2)"

#### 2.9 Devolución (semantic DELETE)
- ✅ Devolución procesada vía PUB/SUB
- ✅ `actor_devolucion` actualizó estado: `ACTIVO` → `DEVUELTO`
- ✅ Ejemplares restaurados: 4 → 5

---

### PARTE 5: Simulación de Fallo y Failover

#### 5.1 Snapshot Pre-Failover
```
Estado antes del failover:
- Libros: 5
- Préstamos: 2
```

#### 5.2 Simular Fallo
- ✅ `postgres_primary` detenido exitosamente
- ✅ Solo `postgres_replica` corriendo

#### 5.4 Failover Ejecutado
```
✅ postgres_replica está corriendo
waiting for server to promote.... done
server promoted
✅ La réplica fue promovida exitosamente a primario
✅ Inserción exitosa - El nuevo primario acepta escrituras
✅ Failover completado!
```

#### 5.5 Verificación Post-Failover
- ✅ `pg_is_in_recovery()` = `f` (false) → Ya es primario
- ⚠️  Libros aumentaron de 5 a 6 (el script de failover insertó un libro de prueba `FAIL-MMddHHmm`)
- ✅ Préstamos preservados: 2

#### 5.6 Prueba Post-Failover
- ❌ **Gestor Almacenamiento no reconectó automáticamente**
- Error: `"connection already closed"`
- **Causa**: El gestor sigue configurado para conectar a `postgres_primary:5432` (caído)
- **El nuevo primario está en**: `postgres_replica:5433`

---

## 📊 Métricas del Sistema

| Operación | Resultado |
|-----------|-----------|
| Consulta ZMQ | ✅ Exitosa |
| Préstamo (CREATE) | ✅ Exitosa |
| Renovación 1 | ✅ Exitosa |
| Renovación 2 | ✅ Exitosa |
| Renovación 3 (límite) | ✅ Rechazada correctamente |
| Devolución | ✅ Exitosa |
| Replicación Primary→Replica | ✅ < 5 segundos |
| Failover manual | ✅ Exitosa (~15 segundos) |
| Preservación de datos | ✅ 100% de préstamos intactos |
| Reconexión automática | ❌ Requiere configuración adicional |

---

## 🎯 Funcionalidades Demostradas

### ✅ Sistema de Mensajería
- **ZMQ REQ/REP**: Cliente ↔ Gestor Carga ↔ Gestor Almacenamiento
- **ZMQ PUB/SUB**: Gest Carga → Actores (préstamo, devolución)
- **Procesamiento síncrono**: Renovación con validación inmediata
- **Procesamiento asíncrono**: Préstamo y devolución vía eventos

### ✅ Lógica de Negocio
- Validación de existencia de libro antes de préstamo
- Límite de renovaciones (máximo 2)
- Decremento/incremento automático de ejemplares
- Estados de préstamo (ACTIVO → DEVUELTO)

### ✅ Replicación y Alta Disponibilidad
- Streaming replication PostgreSQL Primary → Replica
- Failover manual funcional
- Promoción de réplica a primario en ~15 segundos
- Preservación de datos post-failover

---

## ⚠️  Limitación Identificada: Reconexión del Gestor

**Problema**: El `gestor_almacenamiento` no se reconecta automáticamente después del failover.

**Soluciones Posibles**:

### Opción 1: Actualizar servicio manualmente

```powershell
# Detener y recrear el gestor apuntando al nuevo primario
docker stop gestor_almacenamiento
docker rm gestor_almacenamiento

# Editar docker-compose.yml: cambiar DB_HOST a postgres_replica

# Reiniciar solo el gestor
docker-compose up -d gestor_almacenamiento
```

### Opción 2: Usar la lógica de failover existente

El código ya tiene `connect_db_with_failover()` en `gestor_a.py`:
- Intenta conectar a `DB_HOST` (postgres_primary)
- Si falla, intenta `DB_STANDBY_HOST` (postgres_standby)

**Para que funcione**, actualizar en `docker-compose.yml`:
```yaml
environment:
  DB_HOST: postgres_primary
  DB_STANDBY_HOST: postgres_replica  # Cambiar de postgres_standby
```

### Opción 3: Usar un proxy/balanceador (producción)
- PgBouncer o HAProxy detectando automáticamente el primario actual

---

## 🎓 Conclusión para Demostración Académica

Esta prueba demuestra exitosamente:

1. ✅ **Sistema Distribuido Completo**: Múltiples componentes comunicándose vía ZMQ
2. ✅ **Arquitectura de Microservicios**: Gestores y actores independientes
3. ✅ **Patrones de Mensajería**: REQ/REP (síncrono) y PUB/SUB (asíncrono)
4. ✅ **Persistencia con Replicación**: PostgreSQL streaming replication
5. ✅ **Tolerancia a Fallos**: Failover manual funcional con preservación de datos
6. ✅ **Lógica de Negocio Compleja**: Validaciones, límites, transiciones de estado

**Limitación conocida**: La reconexión automática requiere configuración adicional del `docker-compose.yml`, que es un paso manual pero documentado.

**Para producción real**: Se recomendaría Patroni, Repmgr con automatic failover, o un proxy como PgBouncer.

---

## 📝 Archivos Generados

- `test_cliente.py` - Cliente ZMQ para enviar mensajes
- `PRUEBA_END_TO_END.md` - Guía completa de pruebas
- `failover-to-replica.ps1` - Script de failover automático
- `RESUMEN_PRUEBA.md` - Este resumen

---

<Generado el: 2025-11-20 18:28:00>
