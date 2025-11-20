#!/bin/bash
set -e

# Si no hay datos, hacemos el backup base
if [ ! -s "$PGDATA/PG_VERSION" ]; then
    echo "Waiting for primary to be ready..."
    until pg_isready -h postgres_primary -p 5432 -U app; do
        sleep 2
    done

    echo "Starting base backup..."
    PGPASSWORD=replicator_password pg_basebackup -h postgres_primary -D "$PGDATA" -U replicator -v -P --wal-method=stream

    echo "Creating standby.signal..."
    touch "$PGDATA/standby.signal"
    
    # Configurar conexión al primario
    echo "primary_conninfo = 'host=postgres_primary port=5432 user=replicator password=replicator_password application_name=postgres_replica'" >> "$PGDATA/postgresql.auto.conf"
fi

# Ejecutar el entrypoint original de docker
exec docker-entrypoint.sh postgres
