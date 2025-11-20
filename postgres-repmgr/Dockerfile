FROM postgres:16

# Instalar repmgr y dependencias
RUN apt-get update && apt-get install -y \
    postgresql-16-repmgr \
    curl \
    netcat-openbsd \
    gettext-base \
    && rm -rf /var/lib/apt/lists/*

# Copiar scripts de configuración
COPY entrypoint.sh /usr/local/bin/entrypoint-repmgr.sh
COPY repmgr.conf.template /etc/repmgr.conf.template

# Dar permisos de ejecución
RUN chmod +x /usr/local/bin/entrypoint-repmgr.sh

# Usar nuestro entrypoint personalizado
ENTRYPOINT ["/usr/local/bin/entrypoint-repmgr.sh"]
CMD ["postgres"]
