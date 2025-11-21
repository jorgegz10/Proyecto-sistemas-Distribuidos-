FROM postgres:16

# Copiar el script de entrypoint
COPY entrypoint-replica.sh /usr/local/bin/entrypoint-replica.sh

# Convertir formato de línea Windows a Unix y dar permisos de ejecución
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint-replica.sh && \
    chmod +x /usr/local/bin/entrypoint-replica.sh

# Usar el script como entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint-replica.sh"]
