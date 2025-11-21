import subprocess
import time
from datetime import datetime
import sys


# Lista de escenarios de prueba definidos como: (usuarios, tasa de aparición, duración)
escenarios = [
    (4, 2, "2m"),   # 4 usuarios, 2 por segundo durante 2 minutos
    (6, 3, "2m"),   # 6 usuarios, 3 por segundo durante 2 minutos
    (10, 5, "2m"),  # 10 usuarios, 5 por segundo durante 2 minutos
]

print(f"\n🚀 Iniciando {len(escenarios)} escenarios de prueba...\n")

for idx, (usuarios, spawn_rate, duracion) in enumerate(escenarios, 1):
    # Timestamp actual para nombrar los archivos de resultados
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"results_{usuarios}users_{timestamp}"

    print(f"\n{'='*70}")
    print(f"📊 ESCENARIO {idx}/{len(escenarios)}")
    print(f"{'='*70}")
    print(f" Ejecutando prueba con {usuarios} usuarios por {duracion}...")
    print(f" Tasa de aparición: {spawn_rate} usuarios/segundo")
    print(f" Archivo de resultados: {nombre_archivo}")
    print(f"{'='*70}\n")
    sys.stdout.flush()

    # Ruta base del archivo CSV generado por Locust
    csv_base = f"test_results/{nombre_archivo}"

    # Comando para ejecutar Locust en modo headless (sin interfaz web)
    cmd = [
        "locust",
        "--headless",
        "-u", str(usuarios),      # Número de usuarios
        "-r", str(spawn_rate),    # Tasa de aparición
        "-t", duracion,           # Duración
        "-f", "locustfile.py",    # Archivo de definición de usuarios Locust
        "--csv", csv_base,        # Prefijo para los CSVs
        "--only-summary"          # Evita imprimir detalles por endpoint
    ]

    # Ejecutar el comando
    try:
        result = subprocess.run(cmd, check=True)
        print(f"\n✅ Escenario {idx} completado exitosamente\n")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error en escenario {idx}: {e}\n", file=sys.stderr)
        sys.exit(1)
    
    sys.stdout.flush()
    
    if idx < len(escenarios):
        print(f"⏳ Esperando 5 segundos antes del siguiente escenario...\n")
        time.sleep(5)  # Pausa entre escenarios

print("\n" + "="*70)
print("✅ TODAS LAS PRUEBAS HAN FINALIZADO")
print("="*70)
print(f"\n📁 Revisa los resultados en: proceso_solicitante/test_results/\n")