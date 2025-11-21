#!/bin/bash
# Script para promover la réplica a primaria en caso de failover

set -e

echo "=========================================="
echo "PRUEBA DE FAILOVER DE BASE DE DATOS"
echo "=========================================="
echo ""

# 1. Verificar datos replicados
echo "1. Verificando replicación (datos deben ser idénticos)..."
echo "   Primaria:"
docker exec postgres_primary psql -U app -d library -c "SELECT isbn, ejemplares FROM libros;" || echo "Error al conectar con primaria"
echo ""
echo "   Réplica:"
docker exec postgres_replica psql -U app -d library -c "SELECT isbn, ejemplares FROM libros;" || echo "Error al conectar con réplica"
echo ""

# 2. Intentar escribir en réplica (debe fallar)
echo "2. Intentando escribir en réplica (debe fallar - read-only)..."
docker exec postgres_replica psql -U app -d library -c "INSERT INTO libros (isbn, ejemplares) VALUES ('TEST-FAILOVER-01', 10);" 2>&1 | grep -i "read-only" && echo "   ✓ Réplica es read-only correctamente" || echo "   ✗ Error inesperado"
echo ""

# 3. Detener primaria
echo "3. Deteniendo base de datos primaria (simulando falla)..."
docker stop postgres_primary
echo "   ✓ Primaria detenida"
echo ""

# 4. Verificar contenedores
echo "4. Verificando contenedores activos..."
docker ps | grep postgres || echo "   Solo réplica debe estar activa"
echo ""

# 5. Esperar unos segundos
echo "5. Esperando 5 segundos..."
sleep 5

# 6. Promover réplica a primaria
echo "6. Promoviendo réplica a primaria..."
docker exec postgres_replica pg_ctl promote -D /var/lib/postgresql/data
echo "   ✓ Comando de promoción enviado"
echo ""

# 7. Esperar a que la promoción se complete
echo "7. Esperando a que la promoción se complete (15 segundos)..."
sleep 15

# 8. Verificar que ya no está en recovery
echo "8. Verificando que la réplica ahora es primaria..."
docker exec postgres_replica psql -U app -d library -c "SELECT pg_is_in_recovery();" | grep "f" && echo "   ✓ Réplica promovida a primaria exitosamente" || echo "   ✗ Aún en modo recovery"
echo ""

# 9. Intentar escribir en primaria caída (debe fallar)
echo "9. Intentando escribir en primaria caída (debe fallar)..."
docker exec postgres_primary psql -U app -d library -c "INSERT INTO libros (isbn, ejemplares) VALUES ('TEST-FAILOVER-01', 10);" 2>&1 | grep -i "not running" && echo "   ✓ Primaria no responde correctamente" || echo "   Primaria respondió (inesperado)"
echo ""

# 10. Escribir en nueva primaria (debe funcionar)
echo "10. Escribiendo en nueva primaria (antigua réplica)..."
docker exec postgres_replica psql -U app -d library -c "INSERT INTO libros (isbn, ejemplares) VALUES ('TEST-FAILOVER-01', 10);"
echo "   ✓ Escritura exitosa en nueva primaria"
echo ""

# 11. Verificar el nuevo registro
echo "11. Verificando que el nuevo registro existe..."
docker exec postgres_replica psql -U app -d library -c "SELECT isbn, ejemplares FROM libros WHERE isbn = 'TEST-FAILOVER-01';"
echo ""

echo "=========================================="
echo "FAILOVER COMPLETADO EXITOSAMENTE"
echo "=========================================="
