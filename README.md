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

## Deploy

### Local (Desenvolvimento)

```bash
# Clonar repositório
git clone <repository-url>
cd immunotrack

# Executar com Docker Compose
docker-compose up --build

# Ou executar individualmente
cd collector-service
python app.py

cd sensor-service
python app.py
```

### AWS (Produção)

```bash
# Configurar AWS CLI
aws configure

# Executar script de deploy
chmod +x aws-deploy.sh
./aws-deploy.sh
```

## Testes

### Teste Manual

1. **Iniciar Collector:**
```bash
cd collector-service
python app.py
```

2. **Iniciar Sensor:**
```bash
cd sensor-service
python app.py
```

3. **Verificar dados:**
```bash
curl http://localhost:8000/api/temperature/latest
curl http://localhost:8000/health
```

### Teste com Docker

```bash
docker-compose up --build
```

### Teste Automatizado

```bash
python test-system.py
```

## Documentação

- **API Documentation:** [API_DOCUMENTATION.md](./API_DOCUMENTATION.md)
- **Deploy AWS:** [aws-deploy.sh](./aws-deploy.sh)
- **Docker Compose:** [docker-compose.yml](./docker-compose.yml)

## Estrutura do Projeto

```
immunotrack/
├── collector-service/
│   ├── app.py              # API REST principal
│   ├── Dockerfile          # Container do collector
│   └── requirements.txt    # Dependências Python
├── sensor-service/
│   ├── app.py              # Simulador de sensor
│   ├── Dockerfile          # Container do sensor
│   └── requirements.txt    # Dependências Python
├── docker-compose.yml      # Orquestração local
├── aws-deploy.sh          # Script de deploy AWS
├── test-system.py         # Script de testes
├── API_DOCUMENTATION.md    # Documentação da API
└── README.md              # Este arquivo
```

## Status da Entrega

- **Comunicação REST** entre serviços
- **Deploy na nuvem** (AWS)
- **Documentação** técnica completa
- **Base funcional** estabelecida

## Contato

**Equipe:** ImmunoTrack