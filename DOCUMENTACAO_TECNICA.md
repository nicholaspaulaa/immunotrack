# ImmunoTrack - Documentação Técnica

**Sistema de Monitoramento IoT com Arquitetura de Microsserviços**

---

## 1. Visão Geral do Sistema

### 1.1 Objetivo
O ImmunoTrack é um sistema de monitoramento de temperatura para dispositivos IoT, desenvolvido com arquitetura de microsserviços e preparado para deploy na nuvem AWS. O sistema monitora temperaturas de refrigeradores e envia alertas automáticos por email quando detecta condições críticas.

### 1.2 Arquitetura Geral
```
┌─────────────────┐    HTTP/REST    ┌─────────────────┐
│  Sensor Service │ ──────────────► │ Collector Service│
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

## 3. Especificação da API REST

### 3.1 Endpoints do Collector Service

#### 3.1.1 Endpoints de Status
```http
GET /
```
**Descrição:** Status geral do serviço
**Resposta:**
```json
{
  "message": "ImmunoTrack Collector Service",
  "version": "1.0.0",
  "status": "running"
}
```

```http
GET /saude
```
**Descrição:** Health check para monitoramento
**Resposta:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T14:30:00.000Z",
  "service": "collector-service",
  "data_count": 10
}
```

#### 3.1.2 Endpoints de Temperatura
```http
POST /api/temperatura
```
**Descrição:** Recebe dados de temperatura dos sensores
**Corpo da Requisição:**
```json
{
  "id_sensor": "sensor-001",
  "temperatura": 5.23,
  "timestamp": "2024-01-15T14:30:25.123456-03:00"
}
```
**Resposta:**
```json
{
  "message": "Dados recebidos com sucesso",
  "status": "OK"
}
```

```http
GET /api/temperatura/ultima
```
**Descrição:** Retorna a última leitura de temperatura
**Resposta:**
```json
{
  "message": "Última leitura",
  "data": {
    "id_sensor": "sensor-001",
    "temperatura": 5.23,
    "timestamp": "2024-01-15T14:30:25.123456-03:00"
  }
}
```

```http
GET /api/temperatura/todas
```
**Descrição:** Retorna todas as leituras de temperatura
**Resposta:**
```json
[
  {
    "id_sensor": "sensor-001",
    "temperatura": 5.23,
    "timestamp": "2024-01-15T14:30:25.123456-03:00"
  },
  {
    "id_sensor": "sensor-001",
    "temperatura": 4.87,
    "timestamp": "2024-01-15T14:30:35.123456-03:00"
  }
]
```

```http
GET /api/temperatura/contador
```
**Descrição:** Retorna o número total de leituras
**Resposta:**
```json
{
  "count": 150,
  "message": "Total de leituras"
}
```

#### 3.1.3 Endpoints de Alertas
```http
GET /api/alertas
```
**Descrição:** Lista todos os alertas de emergência
**Resposta:**
```json
[
  {
    "id_alerta": "ALERTA_1_20240115_143025",
    "tipo_alerta": "Temperatura Crítica",
    "id_sensor": "sensor-001",
    "temperatura": 15.5,
    "severidade": "CRITICO",
    "mensagem": "Temperatura crítica detectada: 15.5°C - Fora da faixa segura!",
    "timestamp": "2024-01-15T14:30:25.123456-03:00"
  }
]
```

```http
GET /api/alertas/ultimo
```
**Descrição:** Retorna o último alerta gerado

```http
GET /api/alertas/contador
```
**Descrição:** Retorna o número total de alertas

```http
POST /api/alertas/simular
```
**Descrição:** Simula um alerta de emergência para testes

```http
POST /api/alertas/limpar
```
**Descrição:** Limpa todos os alertas armazenados

### 3.2 Endpoints de Interface Web
```http
GET /visualizar
```
**Descrição:** Dashboard principal com visualização de dados

```http
GET /testar-notificacoes
```
**Descrição:** Página para testar notificações por email

```http
GET /simular-emergencia
```
**Descrição:** Página para simular emergências

---

## 4. Sistema de Notificações

### 4.1 Integração AWS SNS
O sistema utiliza AWS Simple Notification Service (SNS) para envio de notificações por email.

**Configuração:**
- **Serviço:** AWS SNS
- **Protocolo:** Email
- **Formato:** HTML + Texto simples (fallback)
- **Região:** us-east-1 (configurável)

### 4.2 Tipos de Alertas
1. **Temperatura Crítica:** Temperatura > 8°C ou < 2°C
2. **Sensor Offline:** Sem dados por mais de 5 minutos
3. **Falha de Energia:** Temperatura = 0°C
4. **Simulação Manual:** Via interface web

### 4.3 Formato do Email
**Assunto:** `ImmunoTrack - [TIPO_ALERTA] - [SEVERIDADE]`

**Conteúdo HTML:**
```html
<html>
<body>
    <h2 style="color: #e74c3c;">ALERTA IMMUNOTRACK</h2>
    
    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">
        <h3>Detalhes do Alerta:</h3>
        <p><strong>Tipo:</strong> Temperatura Crítica</p>
        <p><strong>Sensor:</strong> sensor-001</p>
        <p><strong>Temperatura:</strong> 15.5°C</p>
        <p><strong>Severidade:</strong> CRITICO</p>
        <p><strong>Horário:</strong> 2024-01-15 14:30:25</p>
    </div>
    
    <div style="background: #fff3cd; padding: 15px; border-left: 4px solid #f39c12;">
        <strong>Ação Necessária:</strong> Verificar o refrigerador imediatamente!
    </div>
</body>
</html>
```

---

## 5. Configuração e Deploy

### 5.1 Variáveis de Ambiente
```bash
# Credenciais AWS (OBRIGATÓRIO)
AWS_ACCESS_KEY_ID=sua_access_key_aqui
AWS_SECRET_ACCESS_KEY=sua_secret_key_aqui
AWS_REGION=us-east-1

# Notificações por Email (OBRIGATÓRIO)
EMAIL_NOTIFICACAO=seu-email@exemplo.com

# Configurações do Sistema (OPCIONAL)
DEBUG=True
LOG_LEVEL=INFO
```

### 5.2 Deploy Local com Docker
```bash
# Clonar repositório
git clone <repository-url>
cd immunotrack

# Configurar credenciais
cp configurar-credenciais.txt collector-service/.env
# Editar .env com suas credenciais AWS

# Executar com Docker Compose
docker-compose up --build
```

### 5.3 Deploy Manual
```bash
# Terminal 1 - Collector Service
cd collector-service
python app.py

# Terminal 2 - Sensor Service
cd sensor-service
python app.py
```

### 5.4 Deploy na AWS
```bash
# Configurar AWS CLI
aws configure

# Executar script de deploy
chmod +x aws-deploy.sh
./aws-deploy.sh
```

---

## 6. Monitoramento e Logs

### 6.1 Health Checks
- **Collector Service:** `GET /saude`
- **Docker:** Health check automático a cada 30s
- **Timeout:** 10 segundos
- **Retries:** 3 tentativas

### 6.2 Logs Estruturados
**Formato dos Logs:**
```
INFO:app:Recebido dados do sensor sensor-001: 5.23°C
WARNING:app:ALERTA DE EMERGÊNCIA: Temperatura crítica detectada
ERROR:app:Erro ao enviar notificação AWS: [detalhes do erro]
```

**Níveis de Log:**
- **INFO:** Operações normais
- **WARNING:** Alertas críticos
- **ERROR:** Erros do sistema

### 6.3 Métricas Disponíveis
- Contador de leituras de temperatura
- Contador de alertas gerados
- Status de saúde dos serviços
- Timestamp da última leitura

---

## 7. Segurança

### 7.1 Containerização
- **Usuário não-root** nos containers
- **Imagens base:** python:3.9-slim
- **Dependências mínimas** para reduzir superfície de ataque

### 7.2 Validação de Dados
- **Pydantic** para validação de entrada
- **Timeouts** para evitar travamentos
- **Sanitização** de dados de entrada

### 7.3 Credenciais AWS
- **Variáveis de ambiente** para credenciais
- **Arquivo .gitignore** para proteger dados sensíveis
- **Políticas IAM** com permissões mínimas necessárias

---

## 8. Testes

### 8.1 Teste Manual
```bash
# Verificar status
curl http://localhost:8000/saude

# Enviar dados de teste
curl -X POST http://localhost:8000/api/temperatura \
  -H "Content-Type: application/json" \
  -d '{"id_sensor": "sensor-001", "temperatura": 5.23, "timestamp": "2024-01-15T14:30:25.123456-03:00"}'

# Consultar dados
curl http://localhost:8000/api/temperatura/ultima
```

### 8.2 Teste Automatizado
```bash
# Executar script de teste completo
python test-system.py
```

### 8.3 Teste de Notificações
- Acessar: `http://localhost:8000/testar-notificacoes`
- Clicar em "Testar Notificação por Email"
- Verificar recebimento do email

---

## 9. Troubleshooting

### 9.1 Problemas Comuns

**Erro: "AWS não configurado"**
- Verificar arquivo `.env` na pasta `collector-service`
- Confirmar credenciais AWS válidas
- Verificar permissões IAM para SNS

**Erro: "Porta 8000 já está em uso"**
- Parar outros serviços na porta 8000
- Usar `docker-compose down` antes de subir novamente

**Email não chega**
- Verificar se email está confirmado no AWS SNS
- Verificar logs do sistema para erros
- Testar manualmente via AWS Console

### 9.2 Logs de Debug
```bash
# Ver logs do Docker
docker-compose logs collector-service
docker-compose logs sensor-service

# Ver logs em tempo real
docker-compose logs -f
```

---

## 10. Roadmap e Melhorias Futuras

### 10.1 Funcionalidades Planejadas
- [ ] Banco de dados persistente (PostgreSQL)
- [ ] Autenticação e autorização
- [ ] Dashboard com gráficos em tempo real
- [ ] Múltiplos sensores simultâneos
- [ ] Configuração de limites personalizados

### 10.2 Melhorias Técnicas
- [ ] Métricas com Prometheus
- [ ] Logs centralizados com ELK Stack
- [ ] CI/CD com GitHub Actions
- [ ] Testes automatizados completos
- [ ] Documentação OpenAPI/Swagger

---

## 11. Conclusão

O ImmunoTrack implementa com sucesso uma arquitetura de microsserviços com comunicação REST, preparada para deploy na nuvem AWS. O sistema oferece monitoramento em tempo real, alertas automáticos e uma API REST completa para integração com outros sistemas.

**Principais Conquistas:**
- ✅ Arquitetura de microsserviços implementada
- ✅ Comunicação REST entre serviços
- ✅ Deploy na nuvem AWS preparado
- ✅ Sistema de notificações funcionando
- ✅ Documentação técnica completa
- ✅ Containerização com Docker
- ✅ Monitoramento e health checks

**O sistema está pronto para produção e pode ser facilmente escalado conforme necessário.**
