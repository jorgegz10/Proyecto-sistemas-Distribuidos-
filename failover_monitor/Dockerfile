FROM python:3.11-slim

# Instalar docker CLI para ejecutar comandos docker
RUN apt-get update && \
    apt-get install -y docker.io && \
    rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
RUN pip install --no-cache-dir psycopg2-binary

# Copiar script de monitoreo
COPY monitor.py /app/monitor.py

WORKDIR /app

CMD ["python", "-u", "monitor.py"]
