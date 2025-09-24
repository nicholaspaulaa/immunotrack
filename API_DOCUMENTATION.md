# ImmunoTrack - Documentação da API

**Arquitetura:** Microsserviços REST + AWS

## Visão Geral

O ImmunoTrack é um sistema de monitoramento de temperatura para dispositivos IoT, composto por dois microsserviços principais:

1. **Sensor Service** - Simula sensores de temperatura
2. **Collector Service** - Coleta e armazena dados dos sensores

## Como o Sistema Funciona

O ImmunoTrack funciona de forma simples e eficiente:

**Sensores** → **Coletor** → **Dados Armazenados**

```
Sensores IoT          Servidor Coletor        Banco de Dados
(Simulados)              (FastAPI)                 (Memória)
   
• Gera temperaturas      • Recebe dados via REST   • Armazena leituras
• Envia a cada 10s       • Valida informações      • Disponibiliza via API
• Verifica conexão      • Monitora saúde          • Conta total de dados
```

**Fluxo de Dados:**
1. Sensor gera temperatura aleatória (2°C - 8°C)
2. Envia dados para o coletor via HTTP
3. Coletor valida e armazena os dados
4. API disponibiliza dados para consulta

## Os Dois Serviços Principais

### 1. Collector Service (Servidor Principal)

**O que faz:** Recebe e organiza todos os dados dos sensores  
**Onde roda:** Porta 8000  
**Como acessar:** `http://localhost:8000`

#### Endpoints

##### `GET /`
- **Descrição:** Endpoint raiz do serviço
- **Resposta:**
```json
{
  "message": "ImmunoTrack Collector Service",
  "version": "1.0.0",
  "status": "running"
}
```

##### `GET /health`
- **Descrição:** Health check para monitoramento
- **Resposta:**
```json
{
  "status": "healthy",
  "timestamp": "2025-09-26T10:30:00.000Z",
  "service": "collector-service",
  "data_count": 10
}
```

##### `POST /api/temperature`
- **Descrição:** Recebe dados de temperatura dos sensores
- **Corpo da Requisição (JSON):**
```json
{
  "sensor_id": "sensor-001",
  "temperature": 25.5,
  "timestamp": "2025-09-26T10:30:00.000Z"
}
```
- **Resposta:**
```json
{
  "message": "Dados recebidos com sucesso",
  "status": "OK"
}
```

##### `GET /api/temperature/latest`
- **Descrição:** Retorna a última leitura de temperatura
- **Resposta:**
```json
{
  "message": "Última leitura",
  "data": {
    "sensor_id": "sensor-001",
    "temperature": 25.5,
    "timestamp": "2025-09-26T10:30:00.000Z"
  }
}
```

##### `GET /api/temperature/all`
- **Descrição:** Retorna todas as leituras de temperatura
- **Resposta:**
```json
[
  {
    "sensor_id": "sensor-001",
    "temperature": 25.5,
    "timestamp": "2025-09-26T10:30:00.000Z"
  },
  {
    "sensor_id": "sensor-002",
    "temperature": 26.1,
    "timestamp": "2025-09-26T10:31:00.000Z"
  }
]
```

##### `GET /api/temperature/count`
- **Descrição:** Retorna o número total de leituras
- **Resposta:**
```json
{
  "count": 150,
  "message": "Total de 150 leituras armazenadas"
}
```

### 2. Sensor Service (Simulador de Sensores)

**O que faz:** Simula sensores reais de temperatura, enviando dados constantemente para o coletor

#### Como Funciona

- **Gera temperaturas:** Entre 2.0°C e 8.0°C (faixa realista para vacinas)
- **Intervalo:** A cada 10 segundos (como sensores reais)
- **Se falhar:** Tenta 3 vezes antes de desistir
- **Verifica saúde:** Checa se o coletor está funcionando antes de enviar
- **Logs claros:** Mostra tudo que está acontecendo

#### Configuração

```python
SENSOR_ID = "sensor-001"
COLLECTOR_URL = "http://localhost:8000" # ou http://collector-service:8000 no Docker
INTERVAL = 10 # segundos
```

## Tecnologias Utilizadas

- **Backend:** Python 3.9 + FastAPI
- **Containerização:** Docker + Docker Compose
- **Cloud:** AWS (ECS/EKS + ECR)
- **Monitoramento:** Health checks + Logs estruturados
- **Segurança:** Usuário não-root, timeouts, validação de dados com Pydantic

## Deploy

### Local (Desenvolvimento)

Para rodar o sistema localmente usando Docker Compose:

```bash
# Clonar repositório
git clone <repository-url>
cd immunotrack

# Executar com Docker Compose
docker-compose up --build
```

Ou, para executar os serviços individualmente:

```bash
# Terminal 1: Iniciar Collector Service
cd collector-service
pip install -r requirements.txt
python app.py

# Terminal 2: Iniciar Sensor Service
cd sensor-service
pip install -r requirements.txt
python app.py
```

### AWS (Produção)

Para fazer o deploy na AWS, você pode usar o script `aws-deploy.sh`:

```bash
# 1. Configurar AWS CLI (se ainda não o fez)
aws configure

# 2. Tornar o script executável
chmod +x aws-deploy.sh

# 3. Executar o script de deploy
./aws-deploy.sh
```
Este script irá:
- Criar um repositório ECR (Elastic Container Registry) na AWS.
- Fazer login no ECR.
- Buildar as imagens Docker do Collector e Sensor Service.
- Enviar as imagens para o ECR.

Após a execução do script, as imagens estarão prontas no ECR para serem utilizadas em serviços como AWS ECS (Elastic Container Service) ou AWS EKS (Elastic Kubernetes Service).

## Segurança

- **Usuário não-root** nos containers
- **Health checks** para monitoramento
- **Timeouts** para evitar travamentos
- **Validação de dados** com Pydantic

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

## Conclusão

A comunicação REST entre os serviços está funcional e pronta para deploy na AWS. O sistema possui:

- **Comunicação REST** robusta
- **Health checks** para monitoramento
- **Tratamento de erros** com retry logic
- **Logs estruturados** para debugging
- **Docker** para containerização
- **Scripts de deploy** para AWS
- **Documentação** completa

A base está estabelecida para implementar as próximas funcionalidades da arquitetura completa.