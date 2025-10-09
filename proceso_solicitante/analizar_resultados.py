import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

root = Path(__file__).resolve().parent
archivos = list(root.glob("results_*_stats.csv"))

data = []
for archivo in archivos:
    df = pd.read_csv(archivo)
    df_total = df[df["Name"] == "Total"]
    usuarios = int(str(archivo).split("_")[1].replace("users", ""))
    data.append({
        "Usuarios": usuarios,
        "Tiempo promedio (ms)": df_total["Average Response Time"].values[0],
        "Solicitudes procesadas": df_total["Requests"].values[0],
    })

df_final = pd.DataFrame(data).sort_values("Usuarios")
print(df_final)

plt.figure()
plt.plot(df_final["Usuarios"], df_final["Tiempo promedio (ms)"], marker="o")
plt.title("Tiempo de respuesta promedio vs Nº de usuarios")
plt.xlabel("Usuarios (procesos solicitantes)")
plt.ylabel("Tiempo promedio (ms)")
plt.grid(True)
plt.savefig("grafico_tiempo_respuesta.png")

plt.figure()
plt.plot(df_final["Usuarios"], df_final["Solicitudes procesadas"], marker="s")
plt.title("Solicitudes procesadas vs Nº de usuarios")
plt.xlabel("Usuarios (procesos solicitantes)")
plt.ylabel("Solicitudes procesadas")
plt.grid(True)
plt.savefig("grafico_solicitudes.png")

print("\n✅ Gráficos generados en proceso_solicitante/")
