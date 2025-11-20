# Script de Failover Automático para PostgreSQL
# Este script promueve la réplica a primario en caso de fallo

Write-Host "=== PostgreSQL Failover Script ===" -ForegroundColor Cyan
Write-Host "Este script promoverá postgres_replica a primario`n" -ForegroundColor White

# Verificar que la réplica está corriendo
Write-Host "[CHECK] Verificando que postgres_replica está corriendo..." -ForegroundColor Yellow
$replicaRunning = docker ps --filter "name=postgres_replica" --filter "status=running" --format "{{.Names}}"

if (-not $replicaRunning) {
    Write-Host "❌ ERROR: postgres_replica no está corriendo" -ForegroundColor Red
    exit 1
}
Write-Host "✅ postgres_replica está corriendo`n" -ForegroundColor Green

# 1. Promover réplica a primario
Write-Host "[1/4] Promoviendo réplica a primario..." -ForegroundColor Yellow
docker exec postgres_replica su - postgres -c "/usr/lib/postgresql/16/bin/pg_ctl promote -D /var/lib/postgresql/data"


# 2. Esperar a que termine la promoción
Write-Host "[2/4] Esperando a que complete la promoción..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 3. Verificar que ya no está en recovery mode
Write-Host "[3/4] Verificando que acepta escrituras..." -ForegroundColor Yellow
$recoveryStatus = docker exec postgres_replica psql -U app -d library -tAc "SELECT pg_is_in_recovery();"

if ($recoveryStatus -match "f") {
    Write-Host "✅ La réplica fue promovida exitosamente a primario`n" -ForegroundColor Green
} else {
    Write-Host "⚠️  ADVERTENCIA: El nodo sigue en modo recovery`n" -ForegroundColor Yellow
}

# 4. Test de escritura
Write-Host "[4/4] Probando inserción de datos..." -ForegroundColor Yellow
$timestamp = Get-Date -Format "MMddHHmm"
try {
    docker exec postgres_replica psql -U app -d library -c "INSERT INTO libros (isbn, ejemplares) VALUES ('FAIL-$timestamp', 1);" | Out-Null
    Write-Host "✅ Inserción exitosa - El nuevo primario acepta escrituras`n" -ForegroundColor Green
} catch {
    Write-Host "❌ ERROR: No se pudo insertar datos`n" -ForegroundColor Red
}

# Resumen
Write-Host "=== RESUMEN DEL FAILOVER ===" -ForegroundColor Cyan
Write-Host "Nuevo primario: postgres_replica (puerto 5433)" -ForegroundColor White
Write-Host "`nPasos siguientes:" -ForegroundColor Yellow
Write-Host "1. Actualizar la aplicación para conectar al puerto 5433" -ForegroundColor White
Write-Host "2. Si gestor_almacenamiento tiene failover automático, debería reconectar solo" -ForegroundColor White
Write-Host "3. Verificar logs: docker logs gestor_almacenamiento`n" -ForegroundColor White

Write-Host "✅ Failover completado!" -ForegroundColor Green
