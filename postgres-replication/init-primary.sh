#!/bin/bash
set -e

# Crear usuario de replicación
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD 'replicator_password';
EOSQL

# Configurar pg_hba.conf para permitir replicación
echo "host replication replicator 0.0.0.0/0 scram-sha-256" >> "$PGDATA/pg_hba.conf"

# Recargar configuración (aunque esto corre en initdb, el servidor se reinicia después, así que está bien)
