"""
Sistema de Notificações AWS para ImmunoTrack
Envia email quando há alertas críticos
"""

import boto3
import os
from datetime import datetime, timezone, timedelta
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificadorAWS:
    def __init__(self):
        """Inicializa o cliente AWS SNS"""
        try:
            # Configurar região AWS
            self.region = os.getenv('AWS_REGION', 'us-east-1')
            
            # Criar cliente SNS
            # Usa credenciais padrão do ambiente/role. Se AWS_ACCESS_KEY_ID/SECRET estiverem no env,
            # o boto3 as usará automaticamente; não passamos valores hardcoded.
            self.sns_client = boto3.client(
                'sns',
                region_name=self.region
            )
            
            # Número de telefone para notificações
            self.numero_telefone = os.getenv('TELEFONE_NOTIFICACAO')
            
            # Email para notificações
            self.email_notificacao = os.getenv('EMAIL_NOTIFICACAO')
            
            logger.info("Cliente AWS SNS configurado com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao configurar AWS SNS: {e}")
            self.sns_client = None
    
    def enviar_sms_alerta_critico(self, alerta):
        """Envia SMS para alertas críticos"""
        if not self.sns_client:
            logger.warning("Cliente SNS não configurado")
            return False
        
        try:
            # Formatar mensagem
            mensagem = f"""
ALERTA CRÍTICO IMMUNOTRACK

Tipo: {alerta['tipo_alerta']}
Sensor: {alerta['id_sensor']}
Temperatura: {alerta['temperatura']}°C
Severidade: {alerta['severidade']}
Mensagem: {alerta['mensagem']}
Horário: {alerta['timestamp']}

Ação necessária: Verificar refrigerador imediatamente!
            """.strip()
            
            # Enviar SMS
            response = self.sns_client.publish(
                PhoneNumber=self.numero_telefone,
                Message=mensagem,
                Subject="ImmunoTrack - Alerta Crítico"
            )
            
            logger.info(f"SMS enviado com sucesso: {response['MessageId']}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar SMS: {e}")
            return False
    
    def enviar_email_alerta(self, alerta):
        """Envia email para alertas"""
        if not self.sns_client:
            logger.warning("Cliente SNS não configurado")
            return False
        
        try:
            # Formatar mensagem texto (compatível com assinaturas por email do SNS)
            mensagem_texto = (
                "ALERTA IMMUNOTRACK\n\n"
                f"Tipo: {alerta['tipo_alerta']}\n"
                f"Sensor: {alerta['id_sensor']}\n"
                f"Temperatura: {alerta['temperatura']}°C\n"
                f"Severidade: {alerta['severidade']}\n"
                f"Mensagem: {alerta['mensagem']}\n"
                f"Horário: {alerta['timestamp']}\n\n"
                "Ação necessária: Verificar o refrigerador imediatamente!"
            )
            
            # Enviar email
            response = self.sns_client.publish(
                TopicArn=self.get_topic_arn_email(),
                Message=mensagem_texto,
                Subject=f"ImmunoTrack - {alerta['tipo_alerta']} - {alerta['severidade']}"
            )
            
            logger.info(f"Email enviado com sucesso: {response['MessageId']}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar email: {e}")
            return False
    
    def get_topic_arn_email(self):
        """Obtém o ARN do tópico SNS para email"""
        # Coloque o ARN do email
        return os.getenv('SNS_TOPIC_ARN_EMAIL', 'arn:aws:sns:us-east-1:123456789012:immunotrack-alerts')
    
    def criar_topico_sns(self, nome_topico):
        """Cria um tópico SNS para notificações"""
        try:
            response = self.sns_client.create_topic(Name=nome_topico)
            topic_arn = response['TopicArn']
            logger.info(f"Tópico SNS criado: {topic_arn}")
            return topic_arn
        except Exception as e:
            logger.error(f"Erro ao criar tópico SNS: {e}")
            return None
    
    def inscrever_email(self, email, topic_arn):
        """Inscreve um email no tópico SNS"""
        try:
            response = self.sns_client.subscribe(
                TopicArn=topic_arn,
                Protocol='email',
                Endpoint=email
            )
            logger.info(f"Email {email} inscrito no tópico: {response['SubscriptionArn']}")
            return True
        except Exception as e:
            logger.error(f"Erro ao inscrever email: {e}")
            return False

# Função para integrar com o sistema de alertas
def notificar_alerta_critico(alerta):
    """Função para ser chamada quando há alerta crítico"""
    notificador = NotificadorAWS()
    
    # Enviar SMS para alertas críticos
    if alerta['severidade'] == 'CRITICO':
        notificador.enviar_sms_alerta_critico(alerta)
    
    # Enviar email para todos os alertas
    notificador.enviar_email_alerta(alerta)

# Exemplo de uso
if __name__ == "__main__":
    import os as os_module
