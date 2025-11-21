# 🔄 Sistema de Failover y Resiliencia

## ✅ Implementaciones de Resiliencia

### 1️⃣ **Circuit Breaker** 
**Ubicación:** `common/resilience/circuitBreaker.py`

**Funcionamiento:**
- **CERRADO** → Funcionamiento normal
- **ABIERTO** → Después de 3 fallos consecutivos (no envía peticiones)
- **MEDIO_ABIERTO** → Tras 10 segundos, intenta reconectar

```python
# Estados:
- CERRADO: Servicio funcionando
- ABIERTO: Servicio caído (protege contra sobrecarga)
- MEDIO_ABIERTO: Probando si el servicio volvió
```

---

### 2️⃣ **Failover Automático del Gestor de Almacenamiento**
**Ubicación:** `gestor_carga/gestor.py`

**Características:**
✅ Múltiples endpoints de almacenamiento
✅ Rotación automática cuando uno falla
✅ Circuit breaker por cada endpoint
✅ Reintentos con timeout de 3 segundos
✅ Detecta servicios caídos y usa el siguiente

**Cómo funciona:**
1. Intenta conectar al endpoint actual
2. Si falla o timeout → marca fallo en circuit breaker
3. Rota al siguiente endpoint
4. Repite hasta encontrar uno disponible
5. Si todos fallan → devuelve error al cliente

---

### 3️⃣ **Redundancia de Actores (PUB/SUB)**

**Para Préstamo, Devolución:**
- Múltiples actores se suscriben al mismo tópico
- ZMQ distribuye mensajes automáticamente (round-robin)
- Si un actor cae, los otros siguen procesando

**Ejemplo:**
```
Gestor → Publica "prestamo" 
         ↓
    Actor1 (PC2) ✅ procesa
    Actor2 (PC3) ❌ caído
    
Siguiente mensaje → Actor1 procesa (único disponible)
```

---

## 🔧 Configuración de Failover

### **Configurar múltiples gestores de almacenamiento:**

En `docker-compose.pc1.yml`, agrega variable de entorno:

```yaml
gestor_carga:
  environment:
    - GESTOR_ALMACENAMIENTO_ENDPOINTS=gestor_almacenamiento:5570,backup_almacen:5570
```

Esto permite tener un servidor de respaldo.

---

## 🧪 Probar el Failover

### **Prueba 1: Caída del Gestor de Almacenamiento**

```powershell
# 1. Iniciar todo normalmente
docker-compose -f docker-compose.pc1.yml up -d

# 2. Ejecutar test
python test_sistema.py

# 3. Detener almacenamiento
docker stop gestor_almacenamiento

# 4. Ejecutar test nuevamente
python test_sistema.py
# Verás mensajes de failover intentando reconectar

# 5. Reiniciar almacenamiento
docker start gestor_almacenamiento

# 6. El sistema se recupera automáticamente
python test_sistema.py
```

### **Prueba 2: Caída de un Actor**

```powershell
# 1. En PC2, detener actor_prestamo
docker stop actor_prestamo_pc2

# 2. Desde PC1, ejecutar préstamo
python test_sistema.py

# Resultado: 
# - El mensaje se publica por PUB/SUB
# - Como no hay actor escuchando, no se procesa
# - Pero el gestor NO se bloquea (fire-and-forget)
```

---

## 📊 Logs de Failover

Cuando ocurre un fallo, verás:

```
[Gestor] 🔄 Conectando a tcp://gestor_almacenamiento:5570 (intento 1/4)
[Gestor] ⏱️  Timeout en tcp://gestor_almacenamiento:5570
[Gestor] ⚠️  Circuit breaker ABIERTO para tcp://gestor_almacenamiento:5570
[Gestor] 🔄 Conectando a tcp://backup_almacen:5570 (intento 2/4)
[Gestor] ✅ Conexión exitosa a tcp://backup_almacen:5570
```

---

## 🎯 Resumen de Protecciones

| Componente | Protección | Recuperación |
|------------|-----------|--------------|
| **Gestor Almacenamiento** | Circuit Breaker + Failover | Automática (rota a backup) |
| **Actores (PUB/SUB)** | Redundancia | Manual (reiniciar contenedor) |
| **Gestor Carga** | N/A (punto único crítico) | Requiere reinicio |
| **PostgreSQL** | Volúmenes persistentes | Datos no se pierden |

---

## 🚀 Mejoras Futuras (Opcional)

Si quieres más resiliencia:

1. **Múltiples Gestores de Carga** con load balancer
2. **PostgreSQL con réplicas** (primary + standby)
3. **Health checks activos** (ping periódico a servicios)
4. **Métricas y monitoring** (Prometheus + Grafana)

---

## ✅ Estado Actual

**YA IMPLEMENTADO:**
- ✅ Circuit Breaker funcional
- ✅ Failover del gestor de almacenamiento
- ✅ Timeouts en conexiones
- ✅ Reintentos automáticos
- ✅ Rotación de endpoints
- ✅ Redundancia de actores vía PUB/SUB

**El sistema está listo para manejar fallos de servicios.**
