# ImmunoTrack - Sistema de Monitoramento IoT

**Arquitetura:** Microsserviços REST + AWS

## Visão Geral

O ImmunoTrack é um sistema de monitoramento de temperatura para dispositivos IoT, implementado com arquitetura de microsserviços e preparado para deploy na AWS.

## Arquitetura

```
┌─────────────────┐    HTTP/REST    ┌─────────────────┐
│  Sensor Service │ ──────────────► │ Collector Service│
│                 │                 │                 │
│ - Gera dados    │                 │ - Recebe dados  │
│ - Envia via REST│                 │ - Armazena dados│
│ - Health check  │                 │ - API REST      │
└─────────────────┘                 └─────────────────┘
```

## Serviços

### 1. Sensor Service
- **Função:** Simula sensores de temperatura
- **Comunicação:** HTTP REST para Collector
- **Características:**
  - Gera temperaturas entre 2.0°C e 8.0°C
  - Intervalo configurável (padrão: 10s)
  - Retry logic com 3 tentativas
  - Health check do collector
  - Logs estruturados

### 2. Collector Service  
- **Função:** Coleta e armazena dados dos sensores
- **API:** REST com FastAPI
- **Endpoints:**
  - `GET /` - Status do serviço
  - `GET /health` - Health check
  - `POST /api/temperature` - Recebe dados
  - `GET /api/temperature/latest` - Última leitura
  - `GET /api/temperature/all` - Todas as leituras
  - `GET /api/temperature/count` - Contador

## Tecnologias

- **Backend:** Python 3.9 + FastAPI
- **Containerização:** Docker + Docker Compose
- **Cloud:** AWS (ECS/EKS + ECR)
- **Monitoramento:** Health checks + Logs estruturados
- **Segurança:** Usuário não-root, timeouts, validação

```


