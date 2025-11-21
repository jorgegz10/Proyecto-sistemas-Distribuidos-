# 🖥️ Guía de Ejecución en 3 PCs

## 📊 Distribución de Servicios

```
┌─────────────────────────────────────────────────────────────┐
│  PC1 (LOCAL - SERVIDOR PRINCIPAL)                           │
├─────────────────────────────────────────────────────────────┤
│  ✅ PostgreSQL          (puerto 5432)                       │
│  ✅ Gestor Carga        (puertos 5555, 5556) ⚡ CRÍTICO     │
│  ✅ Gestor Almacenamiento (puerto 5570)                     │
└─────────────────────────────────────────────────────────────┘
                            ↓ ↓ ↓
        ┌───────────────────┴───┴──────────────────┐
        ↓                                          ↓
┌───────────────────────┐              ┌──────────────────────┐
│  PC2 (VIRTUAL 1)      │              │  PC3 (VIRTUAL 2)     │
├───────────────────────┤              ├──────────────────────┤
│  ✅ Actor Préstamo    │              │  ✅ Actor Renovación │
│  ✅ Actor Devolución  │              │                      │
└───────────────────────┘              └──────────────────────┘
```

---

## 🚀 PASO 1: Configurar PC1 (Servidor Principal)

### 1.1 Obtener la IP del PC1
```powershell
ipconfig
```
Anota la IPv4 (ejemplo: `192.168.1.100`)

### 1.2 Configurar Firewall en PC1
```powershell
# Ejecutar como Administrador en PowerShell
New-NetFirewallRule -DisplayName "ZMQ REQ/REP" -Direction Inbound -LocalPort 5555 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "ZMQ PUB/SUB" -Direction Inbound -LocalPort 5556 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Almacenamiento" -Direction Inbound -LocalPort 5570 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "PostgreSQL" -Direction Inbound -LocalPort 5432 -Protocol TCP -Action Allow
```

### 1.3 Iniciar servicios en PC1
```powershell
# Construir imágenes
docker-compose -f docker-compose.pc1.yml build

# Iniciar servicios
docker-compose -f docker-compose.pc1.yml up -d

# Ver logs
docker-compose -f docker-compose.pc1.yml logs -f

# Verificar que están corriendo
docker-compose -f docker-compose.pc1.yml ps
```

---

## 🚀 PASO 2: Configurar PC2 (Actores de Préstamo/Devolución)

### 2.1 Editar docker-compose.pc2.yml
Reemplaza **TODAS** las ocurrencias de `<IP_PC1>` con la IP real del PC1.

**Método rápido con PowerShell:**
```powershell
# Reemplaza 192.168.1.100 con la IP real del PC1
$IP_PC1 = "192.168.1.100"
(Get-Content docker-compose.pc2.yml) -replace '<IP_PC1>', $IP_PC1 | Set-Content docker-compose.pc2.yml
```

### 2.2 Verificar conectividad con PC1
```powershell
Test-NetConnection -ComputerName 192.168.1.100 -Port 5555
Test-NetConnection -ComputerName 192.168.1.100 -Port 5556
Test-NetConnection -ComputerName 192.168.1.100 -Port 5570
```

### 2.3 Iniciar servicios en PC2
```powershell
# Construir imágenes
docker-compose -f docker-compose.pc2.yml build

# Iniciar servicios
docker-compose -f docker-compose.pc2.yml up -d

# Ver logs
docker-compose -f docker-compose.pc2.yml logs -f

# Verificar estado
docker-compose -f docker-compose.pc2.yml ps
```

---

## 🚀 PASO 3: Configurar PC3 (Renovación y Testing)

### 3.1 Editar docker-compose.pc3.yml
Reemplaza **TODAS** las ocurrencias de `<IP_PC1>` con la IP real del PC1.

**Método rápido con PowerShell:**
```powershell
# Reemplaza 192.168.1.100 con la IP real del PC1
$IP_PC1 = "192.168.1.100"
(Get-Content docker-compose.pc3.yml) -replace '<IP_PC1>', $IP_PC1 | Set-Content docker-compose.pc3.yml
```

### 3.2 Verificar conectividad con PC1
```powershell
Test-NetConnection -ComputerName 192.168.1.100 -Port 5555
Test-NetConnection -ComputerName 192.168.1.100 -Port 5556
Test-NetConnection -ComputerName 192.168.1.100 -Port 5570
```

### 3.3 Iniciar servicios en PC3
```powershell
# Construir imágenes
docker-compose -f docker-compose.pc3.yml build

# Iniciar servicios
docker-compose -f docker-compose.pc3.yml up -d

# Ver logs
docker-compose -f docker-compose.pc3.yml logs -f

# Verificar estado
docker-compose -f docker-compose.pc3.yml ps
```

### 3.4 Acceder a Locust Web
Desde cualquier navegador:
```
http://<IP_PC3>:8089
```

---

## 🔍 Verificación del Sistema

### En PC1
```powershell
docker-compose -f docker-compose.pc1.yml ps
docker-compose -f docker-compose.pc1.yml logs gestor_carga
```

### En PC2
```powershell
docker-compose -f docker-compose.pc2.yml ps
docker-compose -f docker-compose.pc2.yml logs actor_prestamo
docker-compose -f docker-compose.pc2.yml logs actor_devolucion
```

### En PC3
```powershell
docker-compose -f docker-compose.pc3.yml ps
docker-compose -f docker-compose.pc3.yml logs actor_renovacion
```

---

## 🛑 Detener los Servicios

### PC1
```powershell
docker-compose -f docker-compose.pc1.yml down
```

### PC2
```powershell
docker-compose -f docker-compose.pc2.yml down
```

### PC3
```powershell
docker-compose -f docker-compose.pc3.yml down
```

---

## ⚠️ Solución de Problemas

### Error: "Connection refused"
1. Verificar que PC1 está ejecutándose
2. Verificar firewall en PC1
3. Verificar que las IPs son correctas en los archivos yml

### Error: "Name resolution failed"
- El `extra_hosts` está mal configurado
- Verificar que reemplazaste `<IP_PC1>` correctamente

### Los actores no reciben mensajes
```powershell
# En PC1, verificar que el gestor publica eventos
docker-compose -f docker-compose.pc1.yml logs -f gestor_carga

# En PC2/PC3, verificar que los actores se conectan
docker-compose -f docker-compose.pc2.yml logs -f
docker-compose -f docker-compose.pc3.yml logs -f
```

### Verificar conectividad de red
```powershell
# Desde PC2 o PC3
ping <IP_PC1>
Test-NetConnection -ComputerName <IP_PC1> -Port 5555
```

---

## 📋 Checklist de Ejecución

- [ ] PC1: Obtener IP del PC1
- [ ] PC1: Configurar firewall
- [ ] PC1: Iniciar servicios
- [ ] PC2: Editar docker-compose.pc2.yml con IP del PC1
- [ ] PC2: Verificar conectividad
- [ ] PC2: Iniciar servicios
- [ ] PC3: Editar docker-compose.pc3.yml con IP del PC1
- [ ] PC3: Verificar conectividad
- [ ] PC3: Iniciar servicios
- [ ] Todos: Verificar logs
- [ ] PC3: Acceder a Locust Web (http://IP_PC3:8089)

---

## 🎯 Orden de Inicio

**IMPORTANTE:** Seguir este orden:

1. **Primero**: PC1 (servidor principal)
2. **Segundo**: PC2 (actores préstamo/devolución)
3. **Tercero**: PC3 (renovación y testing)

**NUNCA** iniciar PC2 o PC3 antes que PC1.

---

## 📊 Puertos Utilizados

| Puerto | Servicio              | PC   | Expuesto |
|--------|-----------------------|------|----------|
| 5432   | PostgreSQL            | PC1  | ✅       |
| 5555   | Gestor Carga REP      | PC1  | ✅       |
| 5556   | Gestor Carga PUB      | PC1  | ✅       |
| 5570   | Gestor Almacenamiento | PC1  | ✅       |
| 8089   | Locust Web            | PC3  | ✅       |
