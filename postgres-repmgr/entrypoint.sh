#!/bin/bash
set -e

# Configuración de variables por defecto
export POSTGRES_DB=${POSTGRES_DB:-library}
export POSTGRES_USER=${POSTGRES_USER:-app}
export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-app}
export REPMGR_PASSWORD=${REPMGR_PASSWORD:-repmgr}
export NODE_ID=${NODE_ID:-1}
export NODE_NAME=${NODE_NAME:-postgres_primary}
export REPMGR_ROLE=${REPMGR_ROLE:-primary}
export PRIMARY_HOST=${PRIMARY_HOST:-postgres_primary}

# Asegurar que el directorio de logs existe
mkdir -p /var/log/postgresql
chown postgres:postgres /var/log/postgresql

# Generar archivo de configuración de repmgr
envsubst < /etc/repmgr.conf.template > /etc/repmgr.conf
chown postgres:postgres /etc/repmgr.conf

echo "====================================="
echo "Iniciando nodo: $NODE_NAME"
echo "Rol: $REPMGR_ROLE"
echo "Node ID: $NODE_ID"
echo "====================================="

# Función para esperar a que PostgreSQL esté listo
wait_for_pg() {
    local host=$1
    local max_attempts=30
    local attempt=0
    
    echo "Esperando a que PostgreSQL en $host esté listo..."
    until pg_isready -h "$host" -U "$POSTGRES_USER" > /dev/null 2>&1 || [ $attempt -eq $max_attempts ]; do
        attempt=$((attempt + 1))
        echo "Intento $attempt/$max_attempts..."
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        echo "ERROR: Timeout esperando a PostgreSQL en $host"
        return 1
    fi
    
    echo "PostgreSQL en $host está listo!"
    return 0
}

# Función para esperar a que el nodo primario esté registrado en repmgr
wait_for_primary_registered() {
    local max_attempts=30
    local attempt=0
    
    echo "Esperando a que el primario esté registrado en repmgr..."
    until PGPASSWORD=$REPMGR_PASSWORD psql -h "$PRIMARY_HOST" -U repmgr -d repmgr -tAc "SELECT 1 FROM repmgr.nodes WHERE type='primary' LIMIT 1" 2>/dev/null | grep -q 1 || [ $attempt -eq $max_attempts ]; do
        attempt=$((attempt + 1))
        echo "Intento $attempt/$max_attempts..."
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        echo "ERROR: Timeout esperando registro del primario en repmgr"
        return 1
    fi
    
    echo "Primario registrado en repmgr!"
    return 0
}

# =============================================================================
# CONFIGURACIÓN PARA NODO PRIMARIO
# =============================================================================
if [ "$REPMGR_ROLE" = "primary" ]; then
    echo "Configurando nodo PRIMARIO..."
    
    # Si el directorio de datos está vacío, inicializar PostgreSQL
    if [ ! -s "$PGDATA/PG_VERSION" ]; then
        echo "Inicializando PostgreSQL..."
        
        # Llamar al entrypoint original de postgres para inicialización
        docker-entrypoint.sh postgres &
        PG_PID=$!
        
        # Esperar a que PostgreSQL esté listo
        wait_for_pg "localhost"
        
        # Crear usuario y base de datos de repmgr
        echo "Creando usuario y base de datos de repmgr..."
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
            CREATE USER repmgr WITH REPLICATION ENCRYPTED PASSWORD '$REPMGR_PASSWORD';
            CREATE DATABASE repmgr OWNER repmgr;
EOSQL
        
        # Configurar pg_hba.conf para repmgr y replicación
        echo "Configurando pg_hba.conf..."
        {
            echo "# Repmgr connections"
            echo "local   repmgr          repmgr                              trust"
            echo "host    repmgr          repmgr      127.0.0.1/32            trust"
            echo "host    repmgr          repmgr      ::1/128                 trust"
            echo "host    repmgr          repmgr      0.0.0.0/0               md5"
            echo "# Replication connections"
            echo "local   replication     repmgr                              trust"
            echo "host    replication     repmgr      127.0.0.1/32            trust"
            echo "host    replication     repmgr      ::1/128                 trust"
            echo "host    replication     repmgr      0.0.0.0/0               md5"
        } >> "$PGDATA/pg_hba.conf"
        
        # Configurar postgresql.conf para replicación
        echo "Configurando postgresql.conf..."
        {
            echo "# Replication settings"
            echo "wal_level = replica"
            echo "max_wal_senders = 10"
            echo "max_replication_slots = 10"
            echo "hot_standby = on"
            echo "hot_standby_feedback = on"
            echo "wal_log_hints = on"
            echo "archive_mode = on"
            echo "archive_command = '/bin/true'"
            echo "# Repmgr settings"
            echo "shared_preload_libraries = 'repmgr'"
        } >> "$PGDATA/postgresql.conf"
        
        # Detener PostgreSQL para que los cambios de configuración se apliquen
        echo "Deteniendo PostgreSQL temporal..."
        kill -TERM $PG_PID
        wait $PG_PID
        
        # Reiniciar PostgreSQL con la nueva configuración
        echo "Reiniciando PostgreSQL con configuración de replicación..."
        docker-entrypoint.sh postgres &
        PG_PID=$!
        wait_for_pg "localhost"
        
        # Crear archivo .pgpass para que repmgr pueda autenticarse
        echo "localhost:5432:repmgr:repmgr:$REPMGR_PASSWORD" > /root/.pgpass
        echo "$NODE_NAME:5432:repmgr:repmgr:$REPMGR_PASSWORD" >> /root/.pgpass
        chmod 0600 /root/.pgpass
        
        # Registrar nodo primario en repmgr
        echo "Registrando nodo primario en repmgr..."
        su - postgres -c "PGPASSWORD=$REPMGR_PASSWORD repmgr -f /etc/repmgr.conf primary register"
        
        # Verificar registro
        echo "Verificando registro..."
        su - postgres -c "PGPASSWORD=$REPMGR_PASSWORD repmgr -f /etc/repmgr.conf cluster show"
        
        # Detener PostgreSQL para que se reinicie con el CMD
        echo "Deteniendo PostgreSQL temporal..."
        kill -TERM $PG_PID
        wait $PG_PID
    fi
    
    # Iniciar PostgreSQL en primer plano
    echo "Iniciando PostgreSQL primario..."
    exec docker-entrypoint.sh postgres &
    PG_PID=$!
    
    # Esperar a que esté listo
    wait_for_pg "localhost"
    
    # Iniciar repmgrd en segundo plano
    echo "Iniciando repmgrd..."
    su - postgres -c "repmgrd -f /etc/repmgr.conf --daemonize=false" &
    
    # Esperar a PostgreSQL (proceso principal)
    wait $PG_PID

# =============================================================================
# CONFIGURACIÓN PARA NODO STANDBY
# =============================================================================
elif [ "$REPMGR_ROLE" = "standby" ]; then
    echo "Configurando nodo STANDBY..."
    
    # Esperar a que el primario esté disponible
    wait_for_pg "$PRIMARY_HOST"
    
    # Esperar a que el primario esté registrado en repmgr
    wait_for_primary_registered
    
    # Si el directorio de datos está vacío, clonar desde el primario
    if [ ! -s "$PGDATA/PG_VERSION" ]; then
        echo "Clonando datos desde el primario..."
        
        # Crear archivo .pgpass para autenticación
        echo "$PRIMARY_HOST:5432:repmgr:repmgr:$REPMGR_PASSWORD" > ~/.pgpass
        chmod 0600 ~/.pgpass
        
        # Clonar usando repmgr
        su - postgres -c "repmgr -h $PRIMARY_HOST -U repmgr -d repmgr -f /etc/repmgr.conf standby clone --fast-checkpoint"
        
        # Limpiar .pgpass
        rm -f ~/.pgpass
    fi
    
    # Iniciar PostgreSQL en primer plano
    echo "Iniciando PostgreSQL standby..."
    exec docker-entrypoint.sh postgres &
    PG_PID=$!
    
    # Esperar a que esté listo
    wait_for_pg "localhost"
    
    # Registrar standby si no está registrado
    echo "Registrando nodo standby en repmgr..."
    if ! su - postgres -c "repmgr -f /etc/repmgr.conf node check --role" | grep -q "standby"; then
        su - postgres -c "repmgr -f /etc/repmgr.conf standby register --force"
    fi
    
    # Verificar registro
    echo "Verificando registro..."
    su - postgres -c "repmgr -f /etc/repmgr.conf cluster show"
    
    # Iniciar repmgrd en segundo plano
    echo "Iniciando repmgrd..."
    su - postgres -c "repmgrd -f /etc/repmgr.conf --daemonize=false" &
    
    # Esperar a PostgreSQL (proceso principal)
    wait $PG_PID

# =============================================================================
# CONFIGURACIÓN PARA NODO WITNESS
# =============================================================================
elif [ "$REPMGR_ROLE" = "witness" ]; then
    echo "Configurando nodo WITNESS..."
    
    # Esperar a que el primario esté disponible
    wait_for_pg "$PRIMARY_HOST"
    
    # Esperar a que el primario esté registrado en repmgr
    wait_for_primary_registered
    
    # Si el directorio de datos está vacío, inicializar PostgreSQL
    if [ ! -s "$PGDATA/PG_VERSION" ]; then
        echo "Inicializando PostgreSQL para witness..."
        
        # Llamar al entrypoint original de postgres para inicialización
        docker-entrypoint.sh postgres &
        PG_PID=$!
        
        # Esperar a que PostgreSQL esté listo
        wait_for_pg "localhost"
        
        # Crear usuario de repmgr
        echo "Creando usuario de repmgr..."
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
            CREATE USER repmgr WITH SUPERUSER ENCRYPTED PASSWORD '$REPMGR_PASSWORD';
EOSQL
        
        # Configurar pg_hba.conf
        echo "Configurando pg_hba.conf..."
        {
            echo "# Repmgr connections"
            echo "local   all             repmgr                              trust"
            echo "host    all             repmgr      127.0.0.1/32            trust"
            echo "host    all             repmgr      0.0.0.0/0               scram-sha-256"
        } >> "$PGDATA/pg_hba.conf"
        
        # Configurar postgresql.conf
        echo "Configurando postgresql.conf..."
        {
            echo "# Repmgr settings"
            echo "shared_preload_libraries = 'repmgr'"
        } >> "$PGDATA/postgresql.conf"
        
        # Recargar configuración
        echo "Recargando configuración de PostgreSQL..."
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c "SELECT pg_reload_conf();"
        
        # Detener PostgreSQL para que se reinicie
        echo "Deteniendo PostgreSQL temporal..."
        kill -TERM $PG_PID
        wait $PG_PID
    fi
    
    # Iniciar PostgreSQL en primer plano
    echo "Iniciando PostgreSQL witness..."
    exec docker-entrypoint.sh postgres &
    PG_PID=$!
    
    # Esperar a que esté listo
    wait_for_pg "localhost"
    
    # Registrar witness
    echo "Registrando nodo witness en repmgr..."
    PGPASSWORD=$REPMGR_PASSWORD repmgr -h "$PRIMARY_HOST" -U repmgr -d repmgr -f /etc/repmgr.conf witness register --force
    
    # Verificar registro
    echo "Verificando registro..."
    PGPASSWORD=$REPMGR_PASSWORD repmgr -h "$PRIMARY_HOST" -U repmgr -d repmgr -f /etc/repmgr.conf cluster show
    
    # Iniciar repmgrd en segundo plano
    echo "Iniciando repmgrd..."
    su - postgres -c "repmgrd -f /etc/repmgr.conf --daemonize=false" &
    
    # Esperar a PostgreSQL (proceso principal)
    wait $PG_PID

else
    echo "ERROR: REPMGR_ROLE debe ser 'primary', 'standby', o 'witness'"
    exit 1
fi
