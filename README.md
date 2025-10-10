# Proyecto - Sistemas Distribuidos

Este repositorio contiene la implementación del proyecto de la asignatura "Sistemas Distribuidos".

En esta aplicación hay varios componentes (actores y gestores) que se comunican mediante ZeroMQ. El diseño permite ejecutar cada componente en máquinas separadas; las conexiones se pueden parametrizar mediante variables de entorno.

## Estructura de carpetas

Raíz del proyecto:

```
docker-compose.yml
README.md
actor_devolucion/
	devolucion.py
	Dockerfile
	requirements.txt
actor_prestamo/
	prestamo.py
	Dockerfile
	requirements.txt
actor_renovacion/
	renovacion.py
	Dockerfile
	requirements.txt
common/
	__init__.py
	actors/
		__init__.py
		base.py
	domain/
		libro.py
		prestamo.py
		tipos.py
		usuario.py
	health/
		monitor.py
		responder.py
	messaging/
		mensaje.py
		peticion.py
		respuesta.py
	resilience/
		circuitBreaker.py
gestor_almacenamiento/
	gestor_a.py
	Dockerfile
	requirements.txt
gestor_carga/
	gestor.py
	Dockerfile
	requirements.txt
proceso_solicitante/
	proceso_solicitante.py
	run_devoluciones.py
	run_renovaciones.py
	solicitudes.txt
	devoluciones.txt
	Dockerfile
	requirements.txt
```

Cada carpeta contiene el código de un servicio/actor y opcionalmente un `Dockerfile` y `requirements.txt` para instalar dependencias.

## Descripción general de la implementación

- `proceso_solicitante`: cliente interactivo que envía peticiones (REQ) al `gestor_carga` (REQ/REP) para solicitar préstamos, consultas o devoluciones.
- `gestor_carga`: orquestador que recibe peticiones del solicitante y publica eventos (PUB) hacia actores especializados (por ejemplo, `renovacion`, `devolucion`) y delega en `gestor_almacenamiento` cuando hace falta.
- `actor_devolucion`: suscrito a eventos de devolución. Realiza llamadas REQ al `gestor_almacenamiento` para aplicar devoluciones.
- `actor_renovacion`: suscrito a eventos de renovación. Valida y actualiza renovaciones mediante REQ al `gestor_almacenamiento`.
- `gestor_almacenamiento`: servicio encargado de la persistencia/estado (simulado en código del proyecto).
- `common/messaging`: contiene clases de mensajes (Peticion, Respuesta, Mensaje base) usadas para serializar y validar mensajes.

La comunicación principal utiliza patrones ZeroMQ:
- REQ/REP entre solicitante <-> gestor_carga y entre actores <-> gestor_almacenamiento.
- PUB/SUB para notificaciones/eventos desde el gestor hacia los actores.

## Variables de entorno para despliegue distribuido

Los endpoints por defecto están configurados para funcionar con Docker Compose (nombres de servicio). Para ejecutar los componentes en máquinas distintas, configura las variables de entorno indicadas antes de lanzar cada servicio.

- `GESTOR_CARGA_ADDR` : dirección completa para conectar REQ al gestor de carga (ej. `tcp://IP_GC:5555`).
- `GESTOR_CARGA_HOST` y `GESTOR_CARGA_PORT` : alternativa por host y puerto.
- `GESTOR_CARGA_PUB_ADDR` : dirección completa del socket PUB del gestor de carga (ej. `tcp://IP_GC:5556`).
- `GESTOR_CARGA_PUB_PORT` : puerto PUB (si se usa `GESTOR_CARGA_HOST`).
- `GESTOR_ALMACENAMIENTO_ADDR` o `GESTOR_ALMACENAMIENTO` : dirección completa del gestor de almacenamiento (ej. `tcp://IP_GA:5570`).

Prioridad de resolución (ej. para `proceso_solicitante`):
1. `GESTOR_CARGA_ADDR` (si está presente usa esa dirección completa).
2. `GESTOR_CARGA_HOST` + `GESTOR_CARGA_PORT`.
3. valor por defecto embebido (p.ej. `tcp://gestor_carga:5555`).

## Cómo correr (sin Docker) — ejemplos en Windows (cmd.exe)

1) Preparar entornos y dependencias

En cada carpeta de servicio hay un `requirements.txt`. Crea y activa un virtualenv y luego instala:

```
python -m venv venv
venv\Scripts\activate
pip install -r <carpeta_servicio>\requirements.txt
```

2) Ejecutar servicios localmente (todos en la misma máquina)

Si vas a probar todo en la misma máquina y estás usando los nombres por defecto del proyecto (p. ej. con Docker Compose), no hace falta setear vars. Para ejecutar manualmente en la misma máquina (con las rutas relativas desde la raíz del repo):

```
cd proceso_solicitante
python proceso_solicitante.py

cd ..\actor_renovacion
python renovacion.py

cd ..\actor_devolucion
python devolucion.py
```

3) Ejecutar componentes en máquinas separadas

Ejemplo: gestor_carga en IP_A, gestor_almacenamiento en IP_B, el solicitante en otra máquina y los actores en otras.

- En la máquina donde correrá `proceso_solicitante` (apunta al gestor_carga en IP_A:5555):

```
set GESTOR_CARGA_ADDR=tcp://IP_A:5555 && python proceso_solicitante.py
```

- En la máquina donde correrá `actor_devolucion` (apunta al gestor_almacenamiento en IP_B:5570):

```
set GESTOR_ALMACENAMIENTO_ADDR=tcp://IP_B:5570 && python devolucion.py
```

- En la máquina donde correrá `actor_renovacion` (suscrito al PUB del gestor_carga en IP_A:5556):

```
set GESTOR_CARGA_PUB_ADDR=tcp://IP_A:5556 && python renovacion.py
```

o alternativamente (host + puerto separados):

```
set GESTOR_CARGA_HOST=IP_A
set GESTOR_CARGA_PUB_PORT=5556
python renovacion.py
```

Notas:
- Asegúrate de que los puertos estén abiertos y accesibles entre máquinas (firewalls, NAT, reglas de red).
- Si usas Docker o docker-compose, exporta estas variables en la definición del servicio o en el entorno del contenedor.

## Cómo correr con Docker Compose

Hay un `docker-compose.yml` en la raíz. Si quieres probar con contenedores en la misma máquina (modo desarrollo):

```
docker-compose up --build
```

Si quieres separar componentes en distintas máquinas con Docker, tendrás que desplegar contenedores en cada host y ajustar las variables de entorno / redes según tu infraestructura (o usar Docker Swarm / Kubernetes).

## Depuración y logs

- Los scripts imprimen mensajes de conexión (p. ej. a qué endpoint ZeroMQ se conectan). Revisa esas salidas para comprobar si usan la dirección esperada.
- Si un REQ falla, revisa timeouts (hay RCVTIMEO/SNDTIMEO configurados) y errores por socket cerrado.

## Video de Presentación del Proyecto

https://drive.google.com/drive/folders/1ObY_77QrREVQ9Y1TRCPwtT7wcZvVRzA3?usp=drive_link



