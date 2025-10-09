FROM python:3.11-slim

WORKDIR /app

# Copiar common (para herencias y mensajes)
COPY ./common /app/common

# Copiar el código del servicio
# Copiar el código del servicio (solo la carpeta del servicio)
COPY ./actor_devolucion /app

# Asegurar requirements en /app (build context es la raíz del repo)
COPY ./actor_devolucion/requirements.txt /app/requirements.txt

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Arranque
CMD ["python", "devolucion.py"]
