import subprocess
import time
from datetime import datetime


# Lista de escenarios de prueba definidos como: (usuarios, tasa de aparición, duración)
escenarios = [
    (4, 2, "2m"),  # 4 usuarios, 2 por segundo durante 2 minutos
    (6, 3, "2m"),  # 6 usuarios, 3 por segundo durante 2 minutos
    (10, 5, "2m"),  # 10 usuarios, 5 por segundo durante 2 minutos
]


for usuarios, spawn_rate, duracion in escenarios:
    # Timestamp actual para nombrar los archivos de resultados
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"results_{usuarios}users_{timestamp}"

    print(f"\n📊 Ejecutando prueba con {usuarios} usuarios por {duracion}...")

    # Ruta base del archivo CSV generado por Locust
    csv_base = f"test_results/results_{usuarios}users_{timestamp}"

    # Comando para ejecutar Locust en modo headless (sin interfaz web)
    cmd = [
        "locust",
        "--headless",
        "-u", str(usuarios),  # Número de usuarios
        "-r", str(spawn_rate),  # Tasa de aparición
        "-t", duracion,  # Duración
        "-f", "locustfile.py",  # Archivo de definición de usuarios Locust
        "--csv", csv_base,  # Prefijo para los CSVs
        "--only-summary"  # Evita imprimir detalles por endpoint
    ]

    # Ejecutar el comando
    subprocess.run(cmd, check=True)
    time.sleep(5)  # Pausa entre escenarios


print("\n✅ Todas las pruebas de RENOVACIÓN han finalizado.")
