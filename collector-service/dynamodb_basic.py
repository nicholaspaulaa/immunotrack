"""
DataBase com DynamoDB
Testando integrações e mudanças com a nova db
"""

import boto3
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from botocore.exceptions import ClientError, NoCredentialsError
from decimal import Decimal

logger = logging.getLogger(__name__)

class DynamoDBService:
    
    def __init__(self):
        try:

            # MUDAR TUDO DAS REGIOES PARA TESTES, SALVO PARA NAO SE PERDER
            self.region = os.getenv('AWS_REGION', 'us-east-1')
            
            self.dynamodb = boto3.resource(
                'dynamodb',
                region_name=self.region,
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
            )
            
            # Nomes das tabelas
            self.temperaturas_table_name = 'immunotrack-temperaturas'
            self.alertas_table_name = 'immunotrack-alertas'
            
            # Referências das tabelas
            self.temperaturas_table = self.dynamodb.Table(self.temperaturas_table_name)
            self.alertas_table = self.dynamodb.Table(self.alertas_table_name)
            
            logger.info(f"DynamoDB conectado na região {self.region}")
            
        except NoCredentialsError:
            logger.error("Credenciais AWS não encontradas")
            raise
        except Exception as e:
            logger.error(f"Erro ao conectar DynamoDB: {e}")
            raise

 # MUDAR TUDO DAS REGIOES PARA TESTES, SALVO PARA NAO SE PERDER
    
    def testar_conexao(self):
        try:
            client = boto3.client('dynamodb', region_name=self.region)
            response = client.list_tables()
            return True
        except Exception as e:
            logger.error(f"Erro ao testar conexão DynamoDB: {e}")
            return False
    
    def _converter_decimal(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self._converter_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._converter_decimal(item) for item in obj]
        return obj
    
    def _gerar_id_temperatura(self, id_sensor: str) -> str:
        fuso_brasilia = timezone(timedelta(hours=-3))
        agora = datetime.now(fuso_brasilia)
        timestamp = agora.strftime('%Y%m%d_%H%M%S_%f')[:-3]
        return f"{id_sensor}#{timestamp}"
    
    def _gerar_id_alerta(self, tipo_alerta: str) -> str:
        fuso_brasilia = timezone(timedelta(hours=-3))
        agora = datetime.now(fuso_brasilia)
        timestamp = agora.strftime('%Y%m%d_%H%M%S_%f')[:-3]
        return f"{tipo_alerta}#{timestamp}"
    
    # TEMPERATURA
    
    def salvar_temperatura(self, id_sensor: str, temperatura: float, timestamp: str) -> Dict:
        try:
            item_id = self._gerar_id_temperatura(id_sensor)
            
            item = {
                'id': item_id,
                'id_sensor': id_sensor,
                'temperatura': Decimal(str(temperatura)),
                'timestamp': timestamp,
                'data_criacao': datetime.now(timezone(timedelta(hours=-3))).isoformat(),
                'tipo_dado': 'temperatura'
            }
            
            self.temperaturas_table.put_item(Item=item)
            logger.info(f"Temperatura salva: {temperatura}°C do sensor {id_sensor}")
            
            return self._converter_decimal(item)
            
        except ClientError as e:
            logger.error(f"Erro ao salvar temperatura no DynamoDB: {e}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao salvar temperatura: {e}")
            raise
    
    def obter_ultima_temperatura(self) -> Optional[Dict]:
        try:
            response = self.temperaturas_table.scan(
                FilterExpression='tipo_dado = :tipo',
                ExpressionAttributeValues={':tipo': 'temperatura'},
                Limit=1000
            )
            
            # Ordenar por tempo // recente
            items = response['Items']
            if items:
                items.sort(key=lambda x: x['data_criacao'], reverse=True)
                return self._converter_decimal(items[0])
            return None
            
        except ClientError as e:
            logger.error(f"Erro ao obter última temperatura: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao obter última temperatura: {e}")
            return None
    
    def obter_todas_temperaturas(self, limite: int = 100) -> List[Dict]:
        try:
            response = self.temperaturas_table.scan(
                FilterExpression='tipo_dado = :tipo',
                ExpressionAttributeValues={':tipo': 'temperatura'},
                Limit=limite
            )
            
            # Ordenar por tempo
            items = response['Items']
            items.sort(key=lambda x: x['data_criacao'], reverse=True)
            
            return [self._converter_decimal(item) for item in items]
            
        except ClientError as e:
            logger.error(f"Erro ao obter temperaturas: {e}")
            return []
        except Exception as e:
            logger.error(f"Erro inesperado ao obter temperaturas: {e}")
            return []
    
    def contar_temperaturas(self) -> int:
        try:
            response = self.temperaturas_table.scan(
                FilterExpression='tipo_dado = :tipo',
                ExpressionAttributeValues={':tipo': 'temperatura'},
                Select='COUNT'
            )
            return response['Count']
            
        except ClientError as e:
            logger.error(f"Erro ao contar temperaturas: {e}")
            return 0
        except Exception as e:
            logger.error(f"Erro inesperado ao contar temperaturas: {e}")
            return 0
    
    # ALERTAS 
    
    def salvar_alerta(self, id_sensor: str, temperatura: float, tipo_alerta: str, 
                     mensagem: str, severidade: str) -> Dict:
        try:
            item_id = self._gerar_id_alerta(tipo_alerta)
            fuso_brasilia = timezone(timedelta(hours=-3))
            agora = datetime.now(fuso_brasilia)
            
            item = {
                'id': item_id,
                'id_sensor': id_sensor,
                'temperatura': Decimal(str(temperatura)),
                'tipo_alerta': tipo_alerta,
                'mensagem': mensagem,
                'severidade': severidade,
                'timestamp': agora.isoformat(),
                'data_criacao': agora.isoformat(),
                'tipo_dado': 'alerta'
            }
            
            self.alertas_table.put_item(Item=item)
            logger.info(f"Alerta salvo: {tipo_alerta} - {severidade}")
            
            return self._converter_decimal(item)
            
        except ClientError as e:
            logger.error(f"Erro ao salvar alerta no DynamoDB: {e}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao salvar alerta: {e}")
            raise
    
    def obter_todos_alertas(self, limite: int = 100) -> List[Dict]:
        try:
            response = self.alertas_table.scan(
                FilterExpression='tipo_dado = :tipo',
                ExpressionAttributeValues={':tipo': 'alerta'},
                Limit=limite
            )
            
            # Ordenar por tempo
            items = response['Items']
            items.sort(key=lambda x: x['data_criacao'], reverse=True)
            
            return [self._converter_decimal(item) for item in items]
            
        except ClientError as e:
            logger.error(f"Erro ao obter alertas: {e}")
            return []
        except Exception as e:
            logger.error(f"Erro inesperado ao obter alertas: {e}")
            return []
    
    def obter_ultimo_alerta(self) -> Optional[Dict]:
        try:
            response = self.alertas_table.scan(
                FilterExpression='tipo_dado = :tipo',
                ExpressionAttributeValues={':tipo': 'alerta'},
                Limit=1000
            )
            
            # Ordenar pelo recente
            items = response['Items']
            if items:
                items.sort(key=lambda x: x['data_criacao'], reverse=True)
                return self._converter_decimal(items[0])
            return None
            
        except ClientError as e:
            logger.error(f"Erro ao obter último alerta: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao obter último alerta: {e}")
            return None
    
    def contar_alertas(self) -> Dict:
        try:
            # Contar os alertas
            response = self.alertas_table.scan(
                FilterExpression='tipo_dado = :tipo',
                ExpressionAttributeValues={':tipo': 'alerta'},
                Select='COUNT'
            )
            
            response_detalhado = self.alertas_table.scan(
                FilterExpression='tipo_dado = :tipo',
                ExpressionAttributeValues={':tipo': 'alerta'}
            )
            
            contadores = {'total': response['Count']}
            for item in response_detalhado['Items']:
                sev = item['severidade']
                contadores[sev] = contadores.get(sev, 0) + 1
            
            return contadores
            
        except ClientError as e:
            logger.error(f"Erro ao contar alertas: {e}")
            return {'total': 0}
        except Exception as e:
            logger.error(f"Erro inesperado ao contar alertas: {e}")
            return {'total': 0}
