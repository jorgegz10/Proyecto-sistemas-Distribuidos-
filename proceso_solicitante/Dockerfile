FROM python:3.11-slim

WORKDIR /app

# Copiar common (para herencias y mensajes)
COPY ./common /app/common

# Copiar el código del servicio
COPY ./proceso_solicitante /app

# Asegurar requirements en /app (build context es la raíz del repo)
COPY ./proceso_solicitante/requirements.txt /app/requirements.txt

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Arranque
CMD ["python", "proceso_solicitante.py"]
