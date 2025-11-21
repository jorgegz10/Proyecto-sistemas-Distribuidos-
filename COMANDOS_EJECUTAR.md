# 🚀 GUÍA RÁPIDA - EJECUCIÓN EN 3 PCS

## 📊 Configuración de IPs:
- **PC1 (Local)**: 192.168.10.12
- **PC2 (win10)**: 192.168.0.8
- **PC3 (win102)**: 192.168.0.9

---

## ⚙️ PASO 1: PC1 (LOCAL) - Tu PC

### Abrir firewall:
```powershell
New-NetFirewallRule -DisplayName "ZMQ REQ/REP" -Direction Inbound -LocalPort 5555 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "ZMQ PUB/SUB" -Direction Inbound -LocalPort 5556 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Almacenamiento" -Direction Inbound -LocalPort 5570 -Protocol TCP -Action Allow
```

### Iniciar gestores:
```powershell
docker-compose -f docker-compose.pc1.yml up -d
```

### Ver logs:
```powershell
docker-compose -f docker-compose.pc1.yml logs -f
```

---

## ⚙️ PASO 2: PC2 (win10 - 192.168.0.8)

### Editar configuración:
```powershell
(Get-Content docker-compose.pc2.yml) -replace '<IP_PC1>', '192.168.10.12' | Set-Content docker-compose.pc2.yml
```

### Verificar conectividad:
```powershell
Test-NetConnection -ComputerName 192.168.10.12 -Port 5555
Test-NetConnection -ComputerName 192.168.10.12 -Port 5556
Test-NetConnection -ComputerName 192.168.10.12 -Port 5570
```

### Iniciar actores:
```powershell
docker-compose -f docker-compose.pc2.yml build
docker-compose -f docker-compose.pc2.yml up -d
```

### Ver logs:
```powershell
docker-compose -f docker-compose.pc2.yml logs -f
```

---

## ⚙️ PASO 3: PC3 (win102 - 192.168.0.9)

### Editar configuración:
```powershell
(Get-Content docker-compose.pc3.yml) -replace '<IP_PC1>', '192.168.10.12' | Set-Content docker-compose.pc3.yml
```

### Verificar conectividad:
```powershell
Test-NetConnection -ComputerName 192.168.10.12 -Port 5555
Test-NetConnection -ComputerName 192.168.10.12 -Port 5556
Test-NetConnection -ComputerName 192.168.10.12 -Port 5570
```

### Iniciar actor:
```powershell
docker-compose -f docker-compose.pc3.yml build
docker-compose -f docker-compose.pc3.yml up -d
```

### Ver logs:
```powershell
docker-compose -f docker-compose.pc3.yml logs -f
```

---

## 🧪 PASO 4: EJECUTAR TEST (desde PC1)

```powershell
# Instalar dependencia si no la tienes
pip install pyzmq

# Ejecutar test
python test_sistema.py
```

---

## ✅ Verificar que todo funciona:

### En PC1:
```powershell
docker-compose -f docker-compose.pc1.yml ps
```
Deberías ver: `gestor_carga`, `gestor_almacenamiento`, `postgres`

### En PC2:
```powershell
docker-compose -f docker-compose.pc2.yml ps
```
Deberías ver: `actor_prestamo_pc2`, `actor_devolucion_pc2`

### En PC3:
```powershell
docker-compose -f docker-compose.pc3.yml ps
```
Deberías ver: `actor_renovacion_pc3`

---

## 🛑 Detener todo:

### PC1:
```powershell
docker-compose -f docker-compose.pc1.yml down
```

### PC2:
```powershell
docker-compose -f docker-compose.pc2.yml down
```

### PC3:
```powershell
docker-compose -f docker-compose.pc3.yml down
```

---

## 🔥 Solución de problemas:

### Si PC2 o PC3 no se conectan:
1. Verificar que PC1 está corriendo: `docker-compose -f docker-compose.pc1.yml ps`
2. Verificar firewall en PC1 (ejecutar comandos del PASO 1)
3. Hacer ping desde la VM: `ping 192.168.10.12`
4. Verificar que Docker Desktop está corriendo en las VMs

### Si el test falla:
1. Ver logs de PC1: `docker-compose -f docker-compose.pc1.yml logs -f`
2. Ver logs de PC2: `docker-compose -f docker-compose.pc2.yml logs -f`
3. Ver logs de PC3: `docker-compose -f docker-compose.pc3.yml logs -f`

### Si hay error de red entre PCs:
- Asegurarse que las VMs usen "Adaptador puente" en VirtualBox
- O configurar "Red NAT" correctamente
