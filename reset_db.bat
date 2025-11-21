# Script para recrear la base de datos con inicialización automática

# Detener y eliminar el contenedor y volumen de postgres
docker-compose down -v postgres
docker volume rm proyecto-sistemas-distribuidos-_postgres_data 2>nul

# Recrear solo postgres con las nuevas configuraciones
docker-compose up -d postgres

# Esperar a que esté listo
timeout /t 5 /nobreak

# Verificar que las tablas se crearon
docker exec postgres_library psql -U app -d library -c "\dt"

# Ver los libros insertados
docker exec postgres_library psql -U app -d library -c "SELECT * FROM libros;"

echo.
echo ========================================
echo Base de datos inicializada correctamente
echo ========================================
