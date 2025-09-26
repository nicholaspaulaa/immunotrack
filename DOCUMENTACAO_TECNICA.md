# ImmunoTrack - Documentação Técnica

**Sistema de Monitoramento IoT com Arquitetura de Microsserviços**

---

## 1. Visão Geral do Sistema

### 1.1 Objetivo
O ImmunoTrack é um sistema de monitoramento de temperatura para dispositivos IoT, desenvolvido com arquitetura de microsserviços e preparado para deploy na nuvem AWS. O sistema monitora temperaturas de refrigeradores e envia alertas automáticos por email quando detecta condições críticas.

### 1.2 Arquitetura Geral
```
┌─────────────────┐    HTTP/REST    ┌─────────────────┐
│  Sensor Service │ ──────────────► │Collector Service│
│                 │                 │                 │
│ - Gera dados    │                 │ - Recebe dados  │
│ - Envia via REST│                 │ - Armazena dados│
│ - Health check  │                 │ - API REST      │
└─────────────────┘                 └─────────────────┘
```

### 1.3 Tecnologias Utilizadas
- **Backend:** Python 3.9 + FastAPI
- **Containerização:** Docker + Docker Compose
- **Cloud:** AWS (SNS para notificações)
- **Comunicação:** REST API (HTTP/JSON)
- **Monitoramento:** Health checks + Logs estruturados

---

## 2. Arquitetura de Microsserviços

### 2.1 Sensor Service
**Responsabilidade:** Simulação de sensores IoT de temperatura

**Características:**
- Gera temperaturas aleatórias entre 2.0°C e 8.0°C
- Intervalo configurável (padrão: 10 segundos)
- Retry logic com 3 tentativas
- Health check do collector antes do envio
- Logs estruturados para monitoramento

**Comunicação:**
- **Protocolo:** HTTP REST
- **Método:** POST
- **Endpoint:** `/api/temperatura`
- **Formato:** JSON

### 2.2 Collector Service
**Responsabilidade:** Coleta, armazenamento e processamento de dados

**Funcionalidades:**
- Recebe dados via API REST
- Armazena dados em memória
- Processa alertas críticos
- Envia notificações por email via AWS SNS
- Interface web para visualização
- API REST para consulta de dados

**Comunicação:**
- **Protocolo:** HTTP REST
- **Framework:** FastAPI
- **Porta:** 8000
- **Endpoints:** Múltiplos endpoints REST

---

## 3. Sistema de Notificações

### 3.1 Integração AWS SNS
O sistema utiliza AWS Simple Notification Service (SNS) para envio de notificações por email.

**Configuração:**
- **Serviço:** AWS SNS
- **Protocolo:** Email
- **Formato:** HTML + Texto simples (fallback)
- **Região:** us-east-1 (configurável)

### 3.2 Tipos de Alertas
1. **Temperatura Crítica:** Temperatura > 8°C ou < 2°C
2. **Sensor Offline:** Sem dados por mais de 5 minutos
3. **Falha de Energia:** Temperatura = 0°C
4. **Simulação Manual:** Via interface web

---

## 4. Monitoramento e Logs

### 4.1 Health Checks
- **Collector Service:** `GET /saude`
- **Docker:** Health check automático a cada 30s
- **Timeout:** 10 segundos
- **Retries:** 3 tentativas

## 5. Melhorias Futuras
- [ ] Banco de dados persistente (DynamoDB)
- [ ] Autenticação e autorização
- [ ] Dashboard com gráficos em tempo real
- [ ] Múltiplos sensores simultâneos



