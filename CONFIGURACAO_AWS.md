# 📱 Configuração de Notificações AWS para ImmunoTrack

## 🚀 Como Configurar Notificações para Celular

### **PASSO 1: Criar Conta AWS**
1. Acesse: https://aws.amazon.com
2. Crie uma conta gratuita
3. Configure pagamento (não será cobrado para uso básico)

### **PASSO 2: Configurar AWS CLI**
1. Instale AWS CLI: https://aws.amazon.com/cli/
2. Execute no terminal:
```bash
aws configure
```
3. Digite suas credenciais:
   - Access Key ID: [sua chave]
   - Secret Access Key: [sua chave secreta]
   - Region: us-east-1
   - Output format: json

### **PASSO 3: Configurar Variáveis de Ambiente**
Crie um arquivo `.env` na pasta do projeto:

```env
# Credenciais AWS
AWS_ACCESS_KEY_ID=sua_access_key_aqui
AWS_SECRET_ACCESS_KEY=sua_secret_key_aqui
AWS_REGION=us-east-1

# Notificações
TELEFONE_NOTIFICACAO=+5511999999999
EMAIL_NOTIFICACAO=seu-email@exemplo.com
```

### **PASSO 4: Instalar Dependências**
```bash
pip install boto3 python-dotenv
```

### **PASSO 5: Testar Notificações**
1. Acesse: http://localhost:8000/simular-emergencia
2. Clique em "Simular Emergência"
3. Verifique seu celular e email

## 💰 Custos Estimados

| Serviço | Custo | Limite Gratuito |
|---------|-------|-----------------|
| SMS (Brasil) | $0.075 por SMS | 100 SMS/mês |
| Email (SES) | Gratuito | 62.000 emails/mês |
| SNS | Gratuito | 1.000.000 notificações/mês |
| **Total Estimado** | **< $5/mês** | Para uso normal |

## 📱 Tipos de Notificação

### **SMS (Apenas Alertas Críticos)**
- Temperatura fora da faixa segura
- Sensor offline
- Falha de energia
- Porta aberta

### **Email (Todos os Alertas)**
- Relatório completo
- Detalhes do alerta
- Ação necessária
- Histórico

### **Dashboard Web**
- Atualização em tempo real
- Gráficos e estatísticas
- Controle total do sistema

## 🔧 Configuração Avançada

### **WhatsApp (Opcional)**
Para notificações via WhatsApp, use:
- Zapier + AWS SNS
- IFTTT + AWS SNS
- Webhook personalizado

### **Telegram (Opcional)**
1. Crie um bot no Telegram
2. Configure webhook
3. Integre com AWS Lambda

## 🚨 Exemplo de Notificação

**SMS:**
```
🚨 ALERTA CRÍTICO IMMUNOTRACK 🚨

Tipo: TEMPERATURA_CRITICA
Sensor: sensor-001
Temperatura: 15.5°C
Severidade: CRITICO
Mensagem: Temperatura crítica detectada!
Horário: 2025-09-25T17:30:00-03:00

Ação necessária: Verificar refrigerador imediatamente!
```

**Email:**
- Assunto: ImmunoTrack - TEMPERATURA_CRITICA - CRITICO
- Conteúdo: Relatório HTML completo com detalhes

## 📊 Monitoramento

### **AWS CloudWatch**
- Logs de notificações
- Métricas de envio
- Alertas de falha

### **Dashboard ImmunoTrack**
- http://localhost:8000/visualizar
- Status em tempo real
- Histórico de alertas

## 🛠️ Solução de Problemas

### **SMS não chega**
1. Verifique formato do telefone: +5511999999999
2. Confirme credenciais AWS
3. Verifique logs: `docker logs immunotrack-collector-service-1`

### **Email não chega**
1. Verifique spam/lixo eletrônico
2. Confirme inscrição no tópico SNS
3. Verifique formato do email

### **AWS não configurado**
1. Execute: `aws configure`
2. Teste: `aws sns list-topics`
3. Verifique permissões IAM

## 📞 Suporte

Para dúvidas sobre AWS:
- Documentação: https://docs.aws.amazon.com/sns/
- Suporte: https://aws.amazon.com/support/
- Comunidade: https://forums.aws.amazon.com/

Para dúvidas sobre ImmunoTrack:
- Dashboard: http://localhost:8000/visualizar
- Logs: `docker logs immunotrack-collector-service-1`
