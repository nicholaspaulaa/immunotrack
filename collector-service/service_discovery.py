"""
Service Discovery para sistema distribuído
Usa Route 53 Private Hosted Zone para descoberta dinâmica de serviços
"""

import boto3
import logging
import os
import socket
import time
from typing import List, Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class ServiceDiscovery:
    """Cliente para descoberta de serviços via Route 53 Private Hosted Zone"""
    
    def __init__(self):
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        self.hosted_zone_id = os.getenv('ROUTE53_HOSTED_ZONE_ID')
        self.service_name = os.getenv('SERVICE_NAME', 'collector')
        self.domain_name = os.getenv('SERVICE_DISCOVERY_DOMAIN', 'internal.immunotrack.local')
        
        # Nome DNS completo do serviço
        self.service_fqdn = f"{self.service_name}.{self.domain_name}"
        
        try:
            self.route53 = boto3.client('route53', region_name=self.region)
            self.ec2 = boto3.client('ec2', region_name=self.region)
            logger.info(f"Service Discovery inicializado para {self.service_fqdn}")
        except Exception as e:
            logger.error(f"Erro ao inicializar Service Discovery: {e}")
            raise
    
    def get_instance_private_ip(self) -> Optional[str]:
        """Obtém o IP privado da instância EC2 atual"""
        try:
            # Método 1: Via metadata service (mais confiável na AWS)
            import urllib.request
            try:
                response = urllib.request.urlopen(
                    'http://169.254.169.254/latest/meta-data/local-ipv4',
                    timeout=2
                )
                return response.read().decode('utf-8')
            except:
                pass
            
            # Método 2: Via hostname (fallback para local/Docker)
            hostname = socket.gethostname()
            try:
                ip = socket.gethostbyname(hostname)
                if not ip.startswith('127.'):
                    return ip
            except:
                pass
            
            # Método 3: Via interfaces de rede
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(('8.8.8.8', 80))
                ip = s.getsockname()[0]
                s.close()
                return ip
            except:
                pass
            
            return None
        except Exception as e:
            logger.error(f"Erro ao obter IP privado: {e}")
            return None
    
    def register_service(self, ttl: int = 60) -> bool:
        """Registra esta instância no Route 53"""
        if not self.hosted_zone_id:
            logger.warning("ROUTE53_HOSTED_ZONE_ID não configurado - registrando apenas em memória local")
            return False
        
        ip = self.get_instance_private_ip()
        if not ip:
            logger.error("Não foi possível obter IP da instância")
            return False
        
        try:
            # Verificar se já existe um registro
            existing_record = self._get_existing_record()
            
            change_batch = {
                'Changes': [{
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': self.service_fqdn,
                        'Type': 'A',
                        'TTL': ttl,
                        'ResourceRecords': [{'Value': ip}]
                    }
                }]
            }
            
            # Se já existir, adicionar outros IPs existentes
            if existing_record:
                existing_ips = {rr['Value'] for rr in existing_record.get('ResourceRecords', [])}
                existing_ips.add(ip)
                change_batch['Changes'][0]['ResourceRecordSet']['ResourceRecords'] = [
                    {'Value': ip_addr} for ip_addr in existing_ips
                ]
            
            response = self.route53.change_resource_record_sets(
                HostedZoneId=self.hosted_zone_id,
                ChangeBatch=change_batch
            )
            
            logger.info(f"Serviço registrado: {self.service_fqdn} -> {ip}")
            return True
            
        except ClientError as e:
            logger.error(f"Erro ao registrar serviço no Route 53: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao registrar serviço: {e}")
            return False
    
    def _get_existing_record(self) -> Optional[dict]:
        """Obtém o registro DNS existente"""
        try:
            response = self.route53.list_resource_record_sets(
                HostedZoneId=self.hosted_zone_id,
                StartRecordName=self.service_fqdn,
                StartRecordType='A',
                MaxItems='1'
            )
            
            records = response.get('ResourceRecordSets', [])
            for record in records:
                if record['Name'] == self.service_fqdn:
                    return record
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar registro existente: {e}")
            return None
    
    def discover_services(self, service_name: Optional[str] = None) -> List[str]:
        """Descobre todas as instâncias de um serviço"""
        if not service_name:
            service_name = self.service_name
        
        service_fqdn = f"{service_name}.{self.domain_name}"
        
        try:
            # Tentar resolver via DNS
            import socket
            try:
                ips = socket.gethostbyname_ex(service_fqdn)[2]
                # Filtrar apenas IPs válidos (não loopback)
                valid_ips = [ip for ip in ips if not ip.startswith('127.')]
                if valid_ips:
                    logger.info(f"Descobertas {len(valid_ips)} instâncias de {service_fqdn}: {valid_ips}")
                    return valid_ips
            except socket.gaierror:
                logger.warning(f"Não foi possível resolver {service_fqdn} via DNS")
            
            # Fallback: buscar via Route 53 API
            if self.hosted_zone_id:
                record = self._get_existing_record()
                if record:
                    ips = [rr['Value'] for rr in record.get('ResourceRecords', [])]
                    logger.info(f"Descobertas {len(ips)} instâncias via Route 53 API: {ips}")
                    return ips
            
            return []
            
        except Exception as e:
            logger.error(f"Erro ao descobrir serviços: {e}")
            return []
    
    def unregister_service(self) -> bool:
        """Remove esta instância do Route 53"""
        if not self.hosted_zone_id:
            return False
        
        ip = self.get_instance_private_ip()
        if not ip:
            return False
        
        try:
            existing_record = self._get_existing_record()
            if not existing_record:
                logger.warning("Registro não encontrado para remover")
                return False
            
            existing_ips = {rr['Value'] for rr in existing_record.get('ResourceRecords', [])}
            existing_ips.discard(ip)
            
            if not existing_ips:
                # Remover registro completamente
                change_batch = {
                    'Changes': [{
                        'Action': 'DELETE',
                        'ResourceRecordSet': existing_record
                    }]
                }
            else:
                # Atualizar com IPs restantes
                change_batch = {
                    'Changes': [{
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': self.service_fqdn,
                            'Type': 'A',
                            'TTL': existing_record.get('TTL', 60),
                            'ResourceRecords': [{'Value': ip_addr} for ip_addr in existing_ips]
                        }
                    }]
                }
            
            self.route53.change_resource_record_sets(
                HostedZoneId=self.hosted_zone_id,
                ChangeBatch=change_batch
            )
            
            logger.info(f"Serviço removido: {self.service_fqdn} (IP: {ip})")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao remover serviço: {e}")
            return False


# Instância global (opcional - pode ser inicializada no app.py)
service_discovery = None


def initialize_service_discovery() -> Optional[ServiceDiscovery]:
    """Inicializa o Service Discovery globalmente"""
    global service_discovery
    try:
        service_discovery = ServiceDiscovery()
        # Auto-registro
        if os.getenv('SERVICE_DISCOVERY_AUTO_REGISTER', 'false').lower() == 'true':
            service_discovery.register_service()
        return service_discovery
    except Exception as e:
        logger.warning(f"Service Discovery não inicializado: {e}")
        return None

