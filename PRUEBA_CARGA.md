# 📈 Pruebas de Carga Automatizadas con Locust y Análisis de Resultados

Este módulo permite ejecutar pruebas de carga automáticas sobre el sistema distribuido usando [Locust](https://locust.io/), guardar resultados como `.csv` y analizarlos para generar gráficas de desempeño.

---

## 🔧 Requisitos previos

- Docker y Docker Compose instalados
- Proyecto clonado y estructurado correctamente con:
  - `docker-compose.yml` configurado
  - Carpetas como `proceso_solicitante`, `common`, `actor_*`, etc.
  - Dockerfiles en cada microservicio

---

## ▶️ Instrucciones paso a paso

### 🧼 1. Limpiar contenedores, volúmenes y red

```bash
docker compose down --volumes --remove-orphans
```

---

### 🛠️ 2. Construir todas las imágenes

```bash
docker compose build
```

---

### 🚀 3. Levantar los servicios base

Incluye gestor de carga, actores y gestor de almacenamiento:

```bash
docker compose up -d \
  gestor_carga \
  gestor_almacenamiento \
  actor_prestamo \
  actor_devolucion \
  actor_renovacion
```

---

### ⏳ 4. Esperar unos segundos

```bash
sleep 5
```

---

### 🧪 5. Ejecutar pruebas automáticas con Locust

Este paso corre el script `run_pruebas_locust.py` desde el servicio `locust_tests`. Esto generará múltiples archivos `.csv`:

```bash
docker compose up locust_tests
```

---

### 📁 6. Verifica que los CSV se generaron

```bash
ls -la proceso_solicitante/test_results
```

Deberías ver archivos similares a:

- `results_4users_*.csv`
- `results_6users_*.csv`
- `results_10users_*.csv`

---

### 📊 7. Analizar resultados y generar gráficos

Esto corre el script `analizar_resultados.py`, que crea:

- `resumen_total.csv`
- `grafico_tiempo_respuesta.png`
- `grafico_solicitudes.png`

```bash
docker compose run --rm analyzer
```

---

### ✅ 8. Verifica los resultados generados

```bash
ls -la proceso_solicitante/test_results/
```

---

### 🧹 9. (Opcional) Limpiar todo nuevamente

```bash
docker compose down --remove-orphans
```

---

## 🧪 Notas

- Los resultados se guardan en `proceso_solicitante/test_results/`
- Puedes modificar el archivo `run_pruebas_locust.py` para ajustar la cantidad de usuarios o duración de las pruebas.
- Si necesitas ejecutar Locust de forma manual con interfaz web:

```bash
docker compose up locust_web
```

Y luego abre en el navegador: [http://localhost:8089](http://localhost:8089)