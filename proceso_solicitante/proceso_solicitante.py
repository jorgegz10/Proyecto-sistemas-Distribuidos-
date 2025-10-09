import subprocess
import time
from datetime import datetime
import os

# Crear directorio para resultados si no existe
os.makedirs("test_results", exist_ok=True)

# Configura tus escenarios: (usuarios, spawn_rate, duración)
escenarios = [
    (4, 2, "2m"),   # 4 usuarios
    (6, 3, "2m"),   # 6 usuarios
    (10, 5, "2m"),  # 10 usuarios
]

# Host del gestor de carga
# Detecta automáticamente si estamos en Docker
import socket
hostname = socket.gethostname()
if "locust" in hostname or os.path.exists("/.dockerenv"):
    HOST = "gestor_carga:5555"  # Dentro de Docker
else:
    HOST = "localhost:5555"  # Desde el host

print(f"🔧 Conectando a: {HOST}")

for usuarios, spawn_rate, duracion in escenarios:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"test_results/results_{usuarios}users_{timestamp}"
    
    print(f"\n🚀 Ejecutando prueba con {usuarios} usuarios por {duracion}...")
    print(f"📊 Resultados se guardarán en: {nombre_archivo}_stats.csv")
    
    cmd = [
        "locust",
        "--headless",
        "-u", str(usuarios),
        "-r", str(spawn_rate),  
        "-t", duracion,
        "-f", "locustfile.py",
        "--host", f"tcp://{HOST}",  # Importante: especificar el host
        "--csv", nombre_archivo,
        "--html", f"{nombre_archivo}_report.html",  # Bonus: reporte HTML
        "--only-summary"
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"✅ Prueba completada. CSV generado: {nombre_archivo}_stats.csv")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error en la prueba: {e}")
    
    time.sleep(5)  # Pausa entre pruebas

print("\n✅ Todas las pruebas han finalizado.")
print(f"📁 Revisa los resultados en la carpeta: test_results/")