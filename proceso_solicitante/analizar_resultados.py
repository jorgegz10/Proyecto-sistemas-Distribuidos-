import pandas as pd






for archivo in archivos:
    df = pd.read_csv(archivo)
    # Filtrar fila con métricas agregadas
    total = df[df["Name"] == "Aggregated"]
    if total.empty:
        continue
    # Extraer número de usuarios desde el nombre del archivo
    nombre = archivo.stem
    try:
        usuarios = int(nombre.split("_")[1].replace("users", ""))
    except Exception:
        usuarios = None


# Guardar estadísticas relevantes
rows.append({
"Usuarios": usuarios,
"Tiempo promedio (ms)": float(total["Average Response Time"].iloc[0]),
"Desv. Std (ms)": None, # Esta columna no está presente
"Solicitudes procesadas": int(total["Request Count"].iloc[0]),
"Requests/s": float(total["Requests/s"].iloc[0]),
})


# Validación
if not rows:
    raise SystemExit("No hubo filas 'Aggregated' en los CSV. Revisa que Locust haya terminado correctamente.")


# Crear dataframe final y guardarlo como CSV
df_final = pd.DataFrame(rows).sort_values("Usuarios")
df_final.to_csv(OUT_DIR / "resumen_total.csv", index=False)
print(df_final)


# Gráfico 1: Tiempo promedio vs Usuarios
plt.figure()
plt.plot(df_final["Usuarios"], df_final["Tiempo promedio (ms)"], marker="o")
plt.title("Tiempo de respuesta promedio vs Nº de usuarios")
plt.xlabel("Usuarios (procesos solicitantes)")
plt.ylabel("Tiempo promedio (ms)")
plt.grid(True)
plt.savefig(OUT_DIR / "grafico_tiempo_respuesta.png", bbox_inches="tight")


# Gráfico 2: Solicitudes procesadas vs Usuarios
plt.figure()
plt.plot(df_final["Usuarios"], df_final["Solicitudes procesadas"], marker="s")
plt.title("Solicitudes procesadas vs Nº de usuarios (2 min)")
plt.xlabel("Usuarios (procesos solicitantes)")
plt.ylabel("Solicitudes procesadas")
plt.grid(True)
plt.savefig(OUT_DIR / "grafico_solicitudes.png", bbox_inches="tight")


print(f"\n Archivos en {OUT_DIR}:")
print(" - resumen_total.csv")
print(" - grafico_tiempo_respuesta.png")
print(" - grafico_solicitudes.png")