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
            self.region = os.getenv('AWS_REGION', 'us-east-1')
            self.endpoint_url = os.getenv('AWS_DYNAMODB_ENDPOINT')
            self.replication_enabled = os.getenv('REPLICATION_LOCAL_ENABLED', 'false').lower() == 'true'
            
            session_kwargs = {
                'region_name': self.region
            }
            access_key = os.getenv('AWS_ACCESS_KEY_ID')
            secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            if access_key and secret_key:
                session_kwargs['aws_access_key_id'] = access_key
                session_kwargs['aws_secret_access_key'] = secret_key

            # Criar cliente/resource de forma não-bloqueante
            # Usar timeout curto e não aguardar conexão completa
            try:
                if self.endpoint_url:
                    self.dynamodb = boto3.resource('dynamodb', endpoint_url=self.endpoint_url, **session_kwargs)
                else:
                    self.dynamodb = boto3.resource('dynamodb', **session_kwargs)
            except Exception as connect_err:
                logger.warning(f"Erro ao criar cliente DynamoDB: {connect_err}")
                raise
            
            # Nomes das tabelas
            self.temperaturas_table_name = 'immunotrack-temperaturas'
            self.alertas_table_name = 'immunotrack-alertas'
            self.temperaturas_replica_table_name = f"{self.temperaturas_table_name}-replica"
            self.alertas_replica_table_name = f"{self.alertas_table_name}-replica"
            
            # Referências das tabelas (lazy - não fazem conexão ainda)
            # Isso acelera muito a inicialização
            self.temperaturas_table = None
            self.alertas_table = None
            self.temperaturas_replica_table = None
            self.alertas_replica_table = None
            
            logger.info(f"DynamoDB cliente criado (região: {self.region}{' - endpoint local' if self.endpoint_url else ''})")
            
        except NoCredentialsError:
            logger.warning("Credenciais AWS não encontradas - DynamoDB desabilitado")
            self.dynamodb = None
            # Não levantar exceção - continuar sem DynamoDB
        except Exception as e:
            logger.warning(f"Erro ao inicializar DynamoDB: {e} - continuando sem DynamoDB")
            self.dynamodb = None
            # Não levantar exceção - permitir que a aplicação continue
    
    def _get_tables(self):
        """Inicializa referências das tabelas lazy (chamado quando necessário)"""
        if not self.dynamodb:
            return
        
        if self.temperaturas_table is None:
            self.temperaturas_table = self.dynamodb.Table(self.temperaturas_table_name)
        if self.alertas_table is None:
            self.alertas_table = self.dynamodb.Table(self.alertas_table_name)
        if self.replication_enabled:
            if self.temperaturas_replica_table is None:
                self.temperaturas_replica_table = self.dynamodb.Table(self.temperaturas_replica_table_name)
            if self.alertas_replica_table is None:
                self.alertas_replica_table = self.dynamodb.Table(self.alertas_replica_table_name)

    def testar_conexao(self):
        try:
            client = boto3.client('dynamodb', region_name=self.region, endpoint_url=self.endpoint_url) if self.endpoint_url else boto3.client('dynamodb', region_name=self.region)
            response = client.list_tables()
            return True
        except Exception as e:
            logger.error(f"Erro ao testar conexão DynamoDB: {e}")
            return False

    def _ensure_tables_exist(self) -> None:
        """Garante que as tabelas existam, mas não trava se houver problemas"""
        try:
            # Criar tabelas de forma não-bloqueante com timeout
            client = boto3.client('dynamodb', region_name=self.region, endpoint_url=self.endpoint_url) if self.endpoint_url else boto3.client('dynamodb', region_name=self.region)

            def ensure_table(name: str):
                try:
                    # Verificar se tabela existe (rápido - timeout curto)
                    client.describe_table(TableName=name)
                    logger.debug(f"Tabela {name} já existe")
                except ClientError as ce:
                    code = ce.response.get('Error', {}).get('Code')
                    if code == 'ResourceNotFoundException':
                        try:
                            logger.info(f"Criando tabela {name} em background...")
                            # Criar tabela sem aguardar
                            client.create_table(
                                TableName=name,
                                AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
                                KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
                                BillingMode='PAY_PER_REQUEST'
                            )
                            logger.info(f"Tabela {name} em criação (não aguardando - será usada quando pronta)")
                            # NÃO aguardar waiter - deixa criar em background
                            # A tabela será usada quando estiver pronta
                        except Exception as create_err:
                            logger.warning(f"Erro ao criar tabela {name}: {create_err}")
                            # Não bloquear - continuar mesmo se não criar agora
                    else:
                        logger.debug(f"Erro ao verificar tabela {name}: {ce}")
                        # Não bloquear por erros de permissão ou outros

            # Criar tabelas principais (não bloquear se falhar)
            ensure_table(self.temperaturas_table_name)
            ensure_table(self.alertas_table_name)
            
            # Criar tabelas de réplica se habilitado
            if self.replication_enabled:
                ensure_table(self.temperaturas_replica_table_name)
                ensure_table(self.alertas_replica_table_name)

        except Exception as e:
            logger.warning(f"Não foi possível garantir criação de tabelas automaticamente: {e}")
            # Não bloquear a inicialização por problemas de tabelas
    
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
        """Salva temperatura no DynamoDB"""
        if not self.dynamodb:
            return {}
        
        # Inicializar tabelas lazy se necessário
        self._get_tables()
        
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
            
            if self.replication_enabled and self.temperaturas_replica_table is not None:
                try:
                    self.temperaturas_replica_table.put_item(Item=item)
                    logger.info("Temperatura replicada na tabela de réplica")
                except Exception as repl_err:
                    logger.warning(f"Falha ao replicar temperatura (write-through): {repl_err}")
            
            return self._converter_decimal(item)
            
        except ClientError as e:
            logger.error(f"Erro ao salvar temperatura no DynamoDB: {e}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao salvar temperatura: {e}")
            raise
    
    def obter_ultima_temperatura(self) -> Optional[Dict]:
        if not self.dynamodb:
            return None
        self._get_tables()
        try:
            response = self.temperaturas_table.scan(
                FilterExpression='tipo_dado = :tipo',
                ExpressionAttributeValues={':tipo': 'temperatura'},
                Limit=1000
            )
            
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
        if not self.dynamodb:
            return []
        self._get_tables()
        try:
            response = self.temperaturas_table.scan(
                FilterExpression='tipo_dado = :tipo',
                ExpressionAttributeValues={':tipo': 'temperatura'},
                Limit=limite
            )
            
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
        if not self.dynamodb:
            return 0
        self._get_tables()
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
        if not self.dynamodb:
            return {}
        self._get_tables()
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
            
            if self.replication_enabled and self.alertas_replica_table is not None:
                try:
                    self.alertas_replica_table.put_item(Item=item)
                    logger.info("Alerta replicado na tabela de réplica")
                except Exception as repl_err:
                    logger.warning(f"Falha ao replicar alerta (write-through): {repl_err}")
            
            return self._converter_decimal(item)
            
        except ClientError as e:
            logger.error(f"Erro ao salvar alerta no DynamoDB: {e}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao salvar alerta: {e}")
            raise
    
    def obter_todos_alertas(self, limite: int = 100) -> List[Dict]:
        if not self.dynamodb:
            return []
        self._get_tables()
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
        if not self.dynamodb:
            return None
        self._get_tables()
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
        if not self.dynamodb:
            return {'total': 0}
        self._get_tables()
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
    
    def marcar_alerta_resolvido(self, alerta_id: str) -> bool:
        """Marca um alerta como resolvido atualizando o campo 'resolvido' para True."""
        try:
            # Buscar o alerta pelo ID
            response = self.alertas_table.get_item(
                Key={'id': alerta_id}
            )
            
            if 'Item' not in response:
                logger.warning(f"Alerta {alerta_id} não encontrado")
                return False
            
            # Atualizar o alerta marcando como resolvido
            self.alertas_table.update_item(
                Key={'id': alerta_id},
                UpdateExpression='SET resolvido = :resolvido, data_resolvido = :data_resolvido',
                ExpressionAttributeValues={
                    ':resolvido': True,
                    ':data_resolvido': datetime.utcnow().isoformat()
                }
            )
            
            logger.info(f"Alerta {alerta_id} marcado como resolvido")
            return True
            
        except ClientError as e:
            logger.error(f"Erro ao marcar alerta como resolvido: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao marcar alerta como resolvido: {e}")
            return False

    # Coordenação distribuída (eleição/locks)

    def adquirir_lease_lider(self, owner_id: str, ttl_seconds: int = 20) -> bool:
        """Tenta adquirir o lease de líder salvando um item na tabela de alertas.
        Apenas uma instância deve conseguir por vez (condicional atômica).
        """
        if not self.dynamodb:
            return False
        
        # Inicializar tabelas lazy se necessário
        self._get_tables()
        
        try:
            fuso_brasilia = timezone(timedelta(hours=-3))
            agora = datetime.now(fuso_brasilia)
            expires_at = (agora + timedelta(seconds=ttl_seconds)).isoformat()

            item = {
                'id': 'leader#collector',
                'tipo_dado': 'leader',
                'ownerId': owner_id,
                'data_criacao': agora.isoformat(),
                'expiresAt': expires_at
            }

            # Condição: item não existe OU expirado
            self.alertas_table.put_item(
                Item=item,
                ConditionExpression='attribute_not_exists(id) OR expiresAt < :now',
                ExpressionAttributeValues={':now': agora.isoformat()}
            )
            return True
        except ClientError as e:
            # Se a condição falhar, outra instância é líder
            if e.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
                return False
            logger.error(f"Erro ao adquirir lease de líder: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao adquirir lease de líder: {e}")
            return False

    def renovar_lease_lider(self, owner_id: str, ttl_seconds: int = 20) -> bool:
        if not self.dynamodb:
            return False
        
        # Inicializar tabelas lazy se necessário
        self._get_tables()
        
        try:
            fuso_brasilia = timezone(timedelta(hours=-3))
            agora = datetime.now(fuso_brasilia)
            expires_at = (agora + timedelta(seconds=ttl_seconds)).isoformat()

            self.alertas_table.update_item(
                Key={'id': 'leader#collector'},
                UpdateExpression='SET expiresAt = :exp',
                ConditionExpression='ownerId = :owner',
                ExpressionAttributeValues={
                    ':exp': expires_at,
                    ':owner': owner_id
                }
            )
            return True
        except ClientError as e:
            # Condição falhou: perdemos a liderança
            if e.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
                return False
            logger.error(f"Erro ao renovar lease de líder: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao renovar lease de líder: {e}")
            return False

    def sou_lider(self, owner_id: str) -> bool:
        if not self.dynamodb:
            return False
        
        # Inicializar tabelas lazy se necessário
        self._get_tables()
        
        try:
            resp = self.alertas_table.get_item(Key={'id': 'leader#collector'})
            item = resp.get('Item')
            if not item:
                return False
            return item.get('ownerId') == owner_id
        except Exception:
            return False

    def marcar_alerta_notificado_uma_vez(self, alerta_id: str) -> bool:
        """Marca alerta como notificado usando Update condicional. Retorna True somente
        se conseguiu marcar agora (ou seja, ninguém marcou antes)."""
        if not self.dynamodb:
            return False
        
        # Inicializar tabelas lazy se necessário
        self._get_tables()
        
        try:
            self.alertas_table.update_item(
                Key={'id': alerta_id},
                UpdateExpression='SET notified = :true, notified_at = :now',
                ConditionExpression='attribute_not_exists(notified) OR notified <> :true',
                ExpressionAttributeValues={
                    ':true': True,
                    ':now': datetime.now(timezone(timedelta(hours=-3))).isoformat()
                }
            )
            return True
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
                return False
            logger.error(f"Erro ao marcar alerta como notificado: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao marcar notificado: {e}")
            return False
    
    def obter_alertas_pendentes_notificacao(self, limite: int = 50) -> List[Dict]:
        """Obtém alertas não notificados ordenados por prioridade (MEDIO > ALTO > CRITICO)"""
        if not self.dynamodb:
            return []
        
        # Inicializar tabelas lazy se necessário
        self._get_tables()
        
        try:
            # Buscar todos os alertas
            response = self.alertas_table.scan(
                FilterExpression='attribute_not_exists(notified) OR notified <> :true',
                ExpressionAttributeValues={':true': True},
                Limit=limite
            )
            
            alertas = response.get('Items', [])
            
            # Ordenar por prioridade: MEDIO > ALTO > CRITICO > outros
            prioridade_map = {'MEDIO': 3, 'ALTO': 2, 'CRITICO': 1}
            
            def prioridade_key(alerta):
                severidade = alerta.get('severidade', 'MEDIO')
                prioridade = prioridade_map.get(severidade, 0)
                timestamp = alerta.get('timestamp') or alerta.get('data_criacao', '')
                return (-prioridade, timestamp)  # Negativo para ordem decrescente
            
            alertas_ordenados = sorted(alertas, key=prioridade_key, reverse=True)
            
            return [self._converter_decimal(a) for a in alertas_ordenados[:limite]]
            
        except Exception as e:
            logger.error(f"Erro ao obter alertas pendentes: {e}")
            return []