SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

PYTHON := python3
PIP := $(PYTHON) -m pip

DOCKER_COMPOSE := docker compose

SERVICES := proceso_solicitante gestor_carga gestor_almacenamiento actor_renovacion actor_devolucion actor_prestamo

.DEFAULT_GOAL := help

help:
	@echo "Makefile (Linux)"
	@echo "Comandos:"
	@echo "  make venv"
	@echo "  make install SERVICE=<servicio>"
	@echo "  make run-local SERVICE=<servicio> [EXTRA_ENV=\"VAR=VAL ...\"]"
	@echo "  make build SERVICE=<servicio>"
	@echo "  make compose-up [SERVICE=<servicio>]"
	@echo "  make compose-down"
	@echo "  make logs SERVICE=<servicio>"
	@echo ""
	@echo "Ej.: make run-local SERVICE=proceso_solicitante EXTRA_ENV=\"GESTOR_CARGA_ADDR=tcp://192.168.1.10:5555\""

venv:
	$(PYTHON) -m venv venv
	@echo "Activa: source venv/bin/activate"

install:
ifndef SERVICE
	$(error Especifica SERVICE=<servicio>)
endif
	@if [ -f "$(SERVICE)/requirements.txt" ]; then \
		echo "Instalando dependencias de $(SERVICE)..."; \
		$(PIP) install -r $(SERVICE)/requirements.txt; \
	else \
		echo "No hay requirements.txt en $(SERVICE)"; \
	fi

# --- Mapeo servicio->script principal (según tu proyecto) ---
ifeq ($(SERVICE),proceso_solicitante)
  SCRIPT := proceso_solicitante.py
endif
ifeq ($(SERVICE),gestor_carga)
  SCRIPT := gestor.py
endif
ifeq ($(SERVICE),gestor_almacenamiento)
  SCRIPT := gestor_a.py
endif
ifeq ($(SERVICE),actor_renovacion)
  SCRIPT := renovacion.py
endif
ifeq ($(SERVICE),actor_devolucion)
  SCRIPT := devolucion.py
endif
ifeq ($(SERVICE),actor_prestamo)
  SCRIPT := prestamo.py
endif

run-local:
ifndef SERVICE
	$(error Especifica SERVICE=<servicio>)
endif
	@echo "Ejecutando $(SERVICE) en local..."
	@cd $(SERVICE) && env $(EXTRA_ENV) $(PYTHON) $(SCRIPT)

build:
ifndef SERVICE
	$(error Especifica SERVICE=<servicio>)
endif
	@echo "Construyendo imagen Docker para $(SERVICE)..."
	docker build -t $(SERVICE):latest $(SERVICE)

compose-up:
ifeq ($(SERVICE),)
	$(DOCKER_COMPOSE) up --build -d
else
	$(DOCKER_COMPOSE) up --build -d $(SERVICE)
endif

compose-down:
	$(DOCKER_COMPOSE) down

logs:
ifndef SERVICE
	$(error Especifica SERVICE=<servicio>)
endif
	$(DOCKER_COMPOSE) logs -f $(SERVICE)

.PHONY: help venv install run-local build compose-up compose-down logs
