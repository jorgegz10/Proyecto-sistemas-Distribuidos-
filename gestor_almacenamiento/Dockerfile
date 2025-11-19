
FROM python:3.11-slim

WORKDIR /app

# Copiar common (para herencias y mensajes)
COPY ./common /app/common

# Copiar el código del servicio
COPY ./gestor_almacenamiento /app

# Asegurar requirements en /app (build context es la raíz del repo)
COPY ./gestor_almacenamiento/requirements.txt /app/requirements.txt

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Arranque (con -u para deshabilitar buffering de Python)
CMD ["python", "-u", "gestor_a.py"]

