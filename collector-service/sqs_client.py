"""
Cliente AWS SQS para comunicação assíncrona entre serviços
Implementa filas priorizadas e dead letter queues
"""

import boto3
import logging
import os
import json
from typing import Optional, Dict, List
from botocore.exceptions import ClientError
from datetime import datetime

logger = logging.getLogger(__name__)


class SQSClient:
    """Cliente para envio e recebimento de mensagens via AWS SQS"""
    
    def __init__(self):
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        self.high_priority_queue_url = os.getenv('SQS_HIGH_PRIORITY_QUEUE_URL')
        self.normal_queue_url = os.getenv('SQS_NORMAL_QUEUE_URL')
        self.dlq_url = os.getenv('SQS_DLQ_URL') 
        
        endpoint_url = os.getenv('AWS_ENDPOINT_URL')
        
        try:
            session_kwargs = {'region_name': self.region}
            
            if endpoint_url:
                session_kwargs['endpoint_url'] = endpoint_url
                logger.info(f"SQS Client inicializado com endpoint local (LocalStack): {endpoint_url}")
            else:
                logger.info("SQS Client inicializado com AWS gerenciado")
            
            access_key = os.getenv('AWS_ACCESS_KEY_ID')
            secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            if access_key and secret_key:
                session_kwargs['aws_access_key_id'] = access_key
                session_kwargs['aws_secret_access_key'] = secret_key
            
            self.sqs = boto3.client('sqs', **session_kwargs)
            logger.info("SQS Client inicializado")
        except Exception as e:
            logger.error(f"Erro ao inicializar SQS Client: {e}")
            raise
    
    def send_message(
        self,
        message_body: Dict,
        priority: str = 'NORMAL',
        delay_seconds: int = 0,
        message_attributes: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Envia mensagem para a fila apropriada
        
        Args:
            message_body: Dicionário com dados da mensagem
            priority: 'HIGH' ou 'NORMAL'
            delay_seconds: Delay opcional antes de processar
            message_attributes: Atributos adicionais da mensagem
        
        Returns:
            MessageId se enviado com sucesso, None caso contrário
        """
        try:
            queue_url = self.high_priority_queue_url if priority == 'HIGH' else self.normal_queue_url
            
            if not queue_url:
                logger.warning(f"Fila {priority} não configurada - mensagem não enviada")
                return None
            
            # Preparar atributos da mensagem
            sqs_attributes = {}
            if message_attributes:
                for key, value in message_attributes.items():
                    sqs_attributes[key] = {
                        'StringValue': str(value),
                        'DataType': 'String'
                    }
            
            # Adicionar timestamp
            sqs_attributes['timestamp'] = {
                'StringValue': datetime.utcnow().isoformat(),
                'DataType': 'String'
            }
            
            # Adicionar priority
            sqs_attributes['priority'] = {
                'StringValue': priority,
                'DataType': 'String'
            }
            
            response = self.sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message_body),
                MessageAttributes=sqs_attributes,
                DelaySeconds=delay_seconds
            )
            
            message_id = response.get('MessageId')
            logger.info(f"Mensagem enviada para fila {priority} (ID: {message_id})")
            return message_id
            
        except ClientError as e:
            logger.error(f"Erro ao enviar mensagem SQS: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar mensagem: {e}")
            return None
    
    def receive_messages(
        self,
        queue_url: Optional[str] = None,
        max_messages: int = 10,
        wait_time_seconds: int = 20,
        visibility_timeout: int = 60
    ) -> List[Dict]:
        """
        Recebe mensagens de uma fila
        
        Args:
            queue_url: URL da fila (se None, usa fila de alta prioridade)
            max_messages: Número máximo de mensagens
            wait_time_seconds: Long polling (0-20)
            visibility_timeout: Tempo de invisibilidade após receber
        
        Returns:
            Lista de mensagens recebidas
        """
        try:
            if not queue_url:
                # Priorizar fila de alta prioridade
                queue_url = self.high_priority_queue_url or self.normal_queue_url
            
            if not queue_url:
                logger.warning("Nenhuma fila configurada para receber mensagens")
                return []
            
            response = self.sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=min(max_messages, 10),  # SQS limita a 10
                WaitTimeSeconds=wait_time_seconds,
                VisibilityTimeout=visibility_timeout,
                MessageAttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            
            if messages:
                logger.info(f"Recebidas {len(messages)} mensagens de {queue_url}")
            
            return messages
            
        except ClientError as e:
            logger.error(f"Erro ao receber mensagens SQS: {e}")
            return []
        except Exception as e:
            logger.error(f"Erro inesperado ao receber mensagens: {e}")
            return []
    
    def delete_message(self, queue_url: str, receipt_handle: str) -> bool:
        """
        Remove mensagem da fila após processamento
        
        Args:
            queue_url: URL da fila
            receipt_handle: Handle da mensagem a ser deletada
        
        Returns:
            True se deletado com sucesso
        """
        try:
            self.sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle
            )
            logger.debug(f"Mensagem deletada da fila {queue_url}")
            return True
            
        except ClientError as e:
            logger.error(f"Erro ao deletar mensagem: {e}")
            return False
    
    def send_to_dlq(self, message_body: Dict, reason: str = "Processing failed") -> Optional[str]:
        """
        Envia mensagem para Dead Letter Queue
        
        Args:
            message_body: Dados da mensagem
            reason: Razão para enviar ao DLQ
        
        Returns:
            MessageId se enviado
        """
        if not self.dlq_url:
            logger.warning("Dead Letter Queue não configurada")
            return None
        
        try:
            message_body_with_reason = {
                **message_body,
                'dlq_reason': reason,
                'dlq_timestamp': datetime.utcnow().isoformat()
            }
            
            response = self.sqs.send_message(
                QueueUrl=self.dlq_url,
                MessageBody=json.dumps(message_body_with_reason),
                MessageAttributes={
                    'reason': {
                        'StringValue': reason,
                        'DataType': 'String'
                    }
                }
            )
            
            logger.warning(f"Mensagem enviada para DLQ: {reason}")
            return response.get('MessageId')
            
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem para DLQ: {e}")
            return None


class SQSMessageHandler:
    """Handler para processar mensagens SQS de forma assíncrona"""
    
    def __init__(self, sqs_client: SQSClient, callback_function):
        """
        Args:
            sqs_client: Instância do SQSClient
            callback_function: Função para processar cada mensagem (recebe dict, retorna bool)
        """
        self.sqs_client = sqs_client
        self.callback = callback_function
        self.running = False
    
    async def start_processing(self, queue_url: Optional[str] = None):
        """Inicia processamento contínuo de mensagens"""
        self.running = True
        import asyncio
        
        while self.running:
            try:
                # Receber mensagens
                messages = self.sqs_client.receive_messages(
                    queue_url=queue_url,
                    wait_time_seconds=20
                )
                
                for message in messages:
                    try:
                        # Parse do body
                        body = json.loads(message['Body'])
                        
                        # Processar via callback
                        success = await self.callback(body)
                        
                        # Se processado com sucesso, deletar da fila
                        if success:
                            self.sqs_client.delete_message(
                                queue_url=queue_url or self.sqs_client.high_priority_queue_url,
                                receipt_handle=message['ReceiptHandle']
                            )
                        else:
                            # Se falhou, enviar para DLQ após algumas tentativas
                            self.sqs_client.send_to_dlq(body, "Callback returned False")
                            self.sqs_client.delete_message(
                                queue_url=queue_url or self.sqs_client.high_priority_queue_url,
                                receipt_handle=message['ReceiptHandle']
                            )
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"Erro ao decodificar mensagem: {e}")
                        self.sqs_client.delete_message(
                            queue_url=queue_url or self.sqs_client.high_priority_queue_url,
                            receipt_handle=message['ReceiptHandle']
                        )
                    except Exception as e:
                        logger.error(f"Erro ao processar mensagem: {e}")
                        # Não deletar - deixar visível novamente após timeout
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Erro no loop de processamento SQS: {e}")
                await asyncio.sleep(5)
    
    def stop_processing(self):
        """Para o processamento de mensagens"""
        self.running = False
        logger.info("Processamento SQS interrompido")


# Instância global
sqs_client = None


def initialize_sqs_client() -> Optional[SQSClient]:
    """Inicializa o cliente SQS globalmente"""
    global sqs_client
    try:
        sqs_client = SQSClient()
        return sqs_client
    except Exception as e:
        logger.warning(f"SQS Client não inicializado: {e}")
        return None

