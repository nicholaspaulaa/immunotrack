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
            self.sns_client = boto3.client(
                'sns',
                region_name=self.region,
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
            )
            
            # Número de telefone para notificações (formato internacional)
            self.numero_telefone = os.getenv('TELEFONE_NOTIFICACAO', '+5511999999999')
            
            # Email para notificações
            self.email_notificacao = os.getenv('EMAIL_NOTIFICACAO', 'seu-email@exemplo.com')
            
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
            # Formatar mensagem HTML
            mensagem_html = f"""
            <html>
            <body>
                <h2 style="color: #e74c3c;">ALERTA IMMUNOTRACK</h2>
                
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3>Detalhes do Alerta:</h3>
                    <p><strong>Tipo:</strong> {alerta['tipo_alerta']}</p>
                    <p><strong>Sensor:</strong> {alerta['id_sensor']}</p>
                    <p><strong>Temperatura:</strong> {alerta['temperatura']}°C</p>
                    <p><strong>Severidade:</strong> {alerta['severidade']}</p>
                    <p><strong>Mensagem:</strong> {alerta['mensagem']}</p>
                    <p><strong>Horário:</strong> {alerta['timestamp']}</p>
                </div>
                
                <div style="background: #fff3cd; padding: 15px; border-radius: 5px; border-left: 4px solid #f39c12;">
                    <strong>Ação Necessária:</strong> Verificar o refrigerador imediatamente!
                </div>
                
                <p style="margin-top: 20px; color: #666;">
                    Este é um alerta automático do sistema ImmunoTrack.
                </p>
            </body>
            </html>
            """
            
            # Enviar email
            response = self.sns_client.publish(
                TopicArn=self.get_topic_arn_email(),
                Message=mensagem_html,
                Subject=f"ImmunoTrack - {alerta['tipo_alerta']} - {alerta['severidade']}",
                MessageAttributes={
                    'content-type': {
                        'DataType': 'String',
                        'StringValue': 'text/html'
                    }
                }
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
