# Prueba del Sistema de Renovaciones

Este documento te guiará paso a paso para probar el caso de uso de renovación de préstamos.

## 📋 Requisitos Previos
- Docker Desktop instalado y ejecutándose
- Todos los archivos del proyecto en su lugar

## 🏗️ Arquitectura de la Prueba

El flujo de renovación funciona así:

1. **proceso_solicitante** (run_renovaciones.py) lee `solicitudes.txt` y envía peticiones de renovación vía REQ/REP
2. **gestor_carga** recibe la petición, calcula nueva_fecha (ahora + 7 días) y responde inmediatamente
3. **gestor_carga** publica evento "renovacion" vía PUB/SUB
4. **actor_renovacion** (suscrito al tópico "renovacion"):
   - Valida con **gestor_almacenamiento** si las renovaciones < 2
   - Si OK: actualiza la renovación (simula UPDATE en BD)
   - Si >= 2: notifica error al gestor_carga
   - Imprime resultado

## 📝 Casos de Prueba en solicitudes.txt

```
RENO Libro456 usuario1  <- Primera renovación (OK)
RENO Libro789 usuario2  <- Primera renovación (OK)
RENO Libro321 usuario3  <- Primera renovación (OK)
RENO Libro456 usuario1  <- Segunda renovación del mismo libro/usuario (OK)
RENO Libro100 usuario4  <- Primera renovación (OK)
```

**Nota**: El gestor de almacenamiento simula que cada préstamo tiene 1 renovación previa. Por lo tanto:
- Primera renovación en solicitudes.txt → renovaciones = 1 → PERMITIDA (se actualiza a 2)
- Segunda renovación del mismo libro/usuario → renovaciones = 2 → DENEGADA (ErrorMaxRenovaciones)

## 🚀 Pasos para Ejecutar la Prueba

### 1️⃣ Construir y levantar todos los servicios

Abre una terminal **cmd** en la raíz del proyecto y ejecuta:

```cmd
docker compose up -d --build
```

Esto construirá y levantará:
- gestor_carga (puertos 5555 y 5556)
- gestor_almacenamiento (puerto 5570)
- actor_renovacion
- actor_prestamo
- actor_devolucion
- proceso_solicitante

### 2️⃣ Verificar que los servicios están corriendo

```cmd
docker compose ps
```

Deberías ver varios contenedores en estado "running".

### 3️⃣ Ver logs en tiempo real (opcional)

Abre terminales separadas para cada servicio:

**Terminal 1 - Gestor de Carga:**
```cmd
docker compose logs -f gestor_carga
```

**Terminal 2 - Gestor de Almacenamiento:**
```cmd
docker compose logs -f gestor_almacenamiento
```

**Terminal 3 - Actor de Renovación:**
```cmd
docker compose logs -f actor_renovacion
```

### 4️⃣ Ejecutar el script de renovaciones

En una nueva terminal:

```cmd
docker compose run --rm run_renovaciones
```

Esto ejecutará el script que lee `solicitudes.txt` y envía las renovaciones al sistema.

## 📊 Qué Esperar Ver

### En run_renovaciones (salida del comando):
```
=== Iniciando envío de renovaciones ===

📤 Enviando renovación: ISBN=Libro456, Usuario=usuario1
📥 Respuesta: {
  "exito": true,
  "mensaje": "ACEPTADO",
  "fechaOperacion": "2025-10-04T...",
  "datos": {
    "nueva_fecha": "2025-10-11T..."
  }
}
------------------------------------------------------------
📤 Enviando renovación: ISBN=Libro456, Usuario=usuario1
📥 Respuesta: ...
------------------------------------------------------------
...
```

### En logs de actor_renovacion:
```
[ActorRenovacion] Procesando mensaje: {...}
renovacion procesada: {'status': 'ok', 'detalle': 'renovacion completada'}
[ActorRenovacion] Resultado: {'ok': True, 'accion': 'renovar_prestamo', 'nueva_fecha': '...'}
```

O cuando se alcanza el límite:
```
renovacion denegada : limite alcanzado
Respuesta gestor_carga a notificarError: ...
```

### En logs de gestor_almacenamiento:
```
[GestorAlmacenamiento] Escuchando en 5570 (REP) - respuestas simuladas
```

### En logs de gestor_carga:
```
Gestor listo en puertos 5555 (REQ/REP) y 5556 (PUB/SUB)
[Gestor] Recibida petición: {'operacion': 'renovacion', 'isbn': 'Libro456', 'usuario': 'usuario1'}
```

## 🔍 Comandos Útiles de Depuración

### Ver logs completos de un servicio:
```cmd
docker compose logs gestor_carga
docker compose logs gestor_almacenamiento
docker compose logs actor_renovacion
```

### Ver logs de todos los servicios:
```cmd
docker compose logs
```

### Reiniciar un servicio específico:
```cmd
docker compose restart actor_renovacion
```

### Detener todos los servicios:
```cmd
docker compose down
```

### Limpiar y reconstruir todo:
```cmd
docker compose down
docker compose up -d --build
```

## 🧪 Modificar Casos de Prueba

Edita el archivo `proceso_solicitante/solicitudes.txt`:
- Cada línea con formato: `RENO <isbn> <usuario>`
- Puedes añadir más líneas para probar diferentes escenarios

Después de modificar, ejecuta de nuevo:
```cmd
docker compose run --rm run_renovaciones
```

## 📈 Escenarios de Prueba Recomendados

1. **Renovación exitosa (primera vez)**:
   - Línea: `RENO LibroNuevo usuarioX`
   - Esperado: "renovacion completada"

2. **Renovación exitosa (segunda vez, mismo libro/usuario)**:
   - Líneas: 
     ```
     RENO Libro999 usuarioY
     RENO Libro999 usuarioY
     ```
   - Esperado: Primera OK, segunda DENEGADA (ErrorMaxRenovaciones)

3. **Múltiples usuarios, mismo libro**:
   - Líneas:
     ```
     RENO LibroPopular user1
     RENO LibroPopular user2
     RENO LibroPopular user3
     ```
   - Esperado: Todas OK (cada usuario tiene su propio contador)

## 🐛 Solución de Problemas

### Problema: "Error al conectar a gestor_carga"
- Verifica que gestor_carga esté corriendo: `docker compose ps`
- Revisa logs: `docker compose logs gestor_carga`

### Problema: "Error al conectar a gestor_almacenamiento"
- Verifica que gestor_almacenamiento esté corriendo
- Revisa logs: `docker compose logs gestor_almacenamiento`

### Problema: Los logs no muestran nada
- Espera unos segundos a que los servicios se inicien completamente
- Usa `docker compose logs -f <servicio>` para ver en tiempo real

### Problema: "renovacion denegada : limite alcanzado" en la primera renovación
- Esto es normal si el gestor de almacenamiento simula que ya hay renovaciones previas
- Para reset: detén y levanta de nuevo los servicios

## 📚 Estructura del Flujo Completo

```
[solicitudes.txt]
       ↓
[run_renovaciones.py] --REQ--> [gestor_carga:5555]
                                      ↓ (responde con nueva_fecha)
                                      ↓ (publica evento "renovacion")
                                      ↓ --PUB--> [actor_renovacion:SUB]
                                                       ↓
                                                       ↓ --REQ--> [gestor_almacenamiento:5570]
                                                       ↓          (valida renovaciones < 2)
                                                       ↓ <--RESP--
                                                       ↓
                                                       ↓ --REQ--> [gestor_almacenamiento:5570]
                                                       ↓          (actualiza renovación)
                                                       ↓ <--RESP-- (ok / ErrorMaxRenovaciones)
                                                       ↓
                                                [imprime resultado]
```

## ✅ Resumen de Comandos

```cmd
# 1. Levantar servicios
docker compose up -d --build

# 2. Ver estado
docker compose ps

# 3. Ejecutar prueba
docker compose run --rm run_renovaciones

# 4. Ver logs (en terminales separadas)
docker compose logs -f gestor_carga
docker compose logs -f gestor_almacenamiento
docker compose logs -f actor_renovacion

# 5. Detener todo
docker compose down
```

---

**¡Listo!** Ahora puedes ejecutar la prueba y observar cómo funciona el sistema de renovaciones end-to-end.
