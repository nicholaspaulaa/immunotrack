"""
Configuração AWS para ImmunoTrack
Instruções para configurar notificações
"""

# ========================================
# CONFIGURAÇÃO AWS SNS PARA NOTIFICAÇÕES
# ========================================

"""
PASSO 1: CRIAR CONTA AWS
1. Acesse: https://aws.amazon.com
2. Crie uma conta gratuita
3. Configure pagamento (não será cobrado para uso básico)

PASSO 2: CONFIGURAR AWS CLI
1. Instale AWS CLI: https://aws.amazon.com/cli/
2. Execute: aws configure
3. Digite suas credenciais:
   - Access Key ID: [sua chave]
   - Secret Access Key: [sua chave secreta]
   - Region: us-east-1
   - Output format: json

PASSO 3: CRIAR TÓPICO SNS
1. Acesse AWS Console > SNS
2. Clique em "Create topic"
3. Nome: immunotrack-alerts
4. Copie o ARN gerado

PASSO 4: CONFIGURAR VARIÁVEIS DE AMBIENTE
Crie um arquivo .env na pasta do projeto:
"""

ENV_EXAMPLE = """
# Arquivo .env - Copie e configure suas credenciais
AWS_ACCESS_KEY_ID=sua_access_key_aqui
AWS_SECRET_ACCESS_KEY=sua_secret_key_aqui
AWS_REGION=us-east-1
TELEFONE_NOTIFICACAO=+5511999999999
EMAIL_NOTIFICACAO=seu-email@exemplo.com
SNS_TOPIC_ARN_EMAIL=arn:aws:sns:us-east-1:123456789012:immunotrack-alerts
"""

# ========================================
# CUSTOS ESTIMADOS (USD)
# ========================================

CUSTOS = {
    "SMS": {
        "Brasil": "$0.075 por SMS",
        "EUA": "$0.0075 por SMS",
        "Gratuito": "Primeiros 100 SMS/mês"
    },
    "Email": {
        "SES": "Gratuito até 62.000 emails/mês",
        "SNS": "Gratuito até 1.000.000 notificações/mês"
    },
    "Total_estimado": "Menos de $5/mês para uso normal"
}

# ========================================
# CÓDIGO PARA CONFIGURAR AUTOMATICAMENTE
# ========================================

def configurar_aws_automaticamente():
    """Configura AWS SNS automaticamente"""
    import boto3
    import os
    
    try:
        # Criar cliente SNS
        sns = boto3.client('sns', region_name='us-east-1')
        
        # Criar tópico para emails
        topic_response = sns.create_topic(Name='immunotrack-alerts')
        topic_arn = topic_response['TopicArn']
        
        print(f"✅ Tópico SNS criado: {topic_arn}")
        
        # Inscrever email
        email = os.getenv('EMAIL_NOTIFICACAO')
        if email:
            subscription = sns.subscribe(
                TopicArn=topic_arn,
                Protocol='email',
                Endpoint=email
            )
            print(f"✅ Email {email} inscrito")
            print("📧 Verifique seu email e confirme a inscrição!")
        
        return topic_arn
        
    except Exception as e:
        print(f"❌ Erro ao configurar AWS: {e}")
        return None

# ========================================
# INSTRUÇÕES DE USO
# ========================================

INSTRUCOES = """
🚀 COMO USAR NOTIFICAÇÕES AWS:

1. CONFIGURAR CREDENCIAIS:
   - Copie o arquivo .env.example para .env
   - Configure suas credenciais AWS
   - Configure seu telefone e email

2. TESTAR NOTIFICAÇÕES:
   - Acesse: http://localhost:8000/simular-emergencia
   - Clique em "Simular Emergência"
   - Verifique seu celular e email

3. TIPOS DE NOTIFICAÇÃO:
   - SMS: Apenas para alertas CRÍTICOS
   - Email: Para todos os alertas
   - Dashboard: Sempre atualizado

4. CUSTOS:
   - SMS: ~$0.075 por mensagem no Brasil
   - Email: Gratuito até 62.000/mês
   - Total estimado: <$5/mês

5. MONITORAMENTO:
   - AWS CloudWatch: Logs e métricas
   - Dashboard: http://localhost:8000/visualizar
   - Alertas: http://localhost:8000/alertas-pagina
"""

if __name__ == "__main__":
    print(INSTRUCOES)
    print("\n" + "="*50)
    print("Configuração automática:")
    configurar_aws_automaticamente()
