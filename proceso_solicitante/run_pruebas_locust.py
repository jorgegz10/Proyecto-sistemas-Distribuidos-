import subprocess
import time
from datetime import datetime

# Configura tus escenarios: (usuarios, spawn_rate, duración)
escenarios = [
    (4, 2, "2m"),   # 4 usuarios
    (6, 3, "2m"),   # 6 usuarios
    (10, 5, "2m"),  # 10 usuarios
]

for usuarios, spawn_rate, duracion in escenarios:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"results_{usuarios}users_{timestamp}"
    
    print(f"\n🚀 Ejecutando prueba con {usuarios} usuarios por {duracion}...")
    
    cmd = [
        "locust",
        "--headless",
        "-u", str(usuarios),
        "-r", str(spawn_rate),  
        "-t", duracion,
        "-f", "locustfile.py",
        "--csv", nombre_archivo,
        "--only-summary"
    ]
    
    subprocess.run(cmd, check=True)
    time.sleep(5)

print("\n✅ Todas las pruebas han finalizado.")
