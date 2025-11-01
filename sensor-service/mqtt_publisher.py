"""
Publicador MQTT para sensores
Permite que sensores publiquem dados via MQTT ao invés de HTTP REST
"""

import paho.mqtt.client as mqtt
import logging
import json
import os
import time
from typing import Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class MQTTSensorPublisher:
    """Publica dados de sensores via MQTT"""
    
    def __init__(
        self,
        broker_host: str = None,
        broker_port: int = 1883,
        client_id: str = None,
        topic_prefix: str = "immunotrack"
    ):
        self.broker_host = broker_host or os.getenv('MQTT_BROKER_HOST', 'mosquitto')
        self.broker_port = int(os.getenv('MQTT_BROKER_PORT', broker_port))
        # Usar SENSOR_ID do ambiente para client_id único, ou gerar UUID
        sensor_id = os.getenv('SENSOR_ID', 'unknown')
        self.client_id = client_id or f"sensor-{sensor_id}-{os.getpid()}-{int(time.time())}"
        self.topic_prefix = topic_prefix
        self.client = None
        self.connected = False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback quando conecta ao broker"""
        if rc == 0:
            self.connected = True
            logger.info(f"[MQTT] Conectado ao broker {self.broker_host}:{self.broker_port}")
        else:
            self.connected = False
            logger.error(f"[MQTT] Falha ao conectar: código {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback quando desconecta do broker"""
        self.connected = False
        logger.warning(f"[MQTT] Desconectado do broker (código {rc})")
    
    def _on_publish(self, client, userdata, mid):
        """Callback quando mensagem é publicada"""
        logger.debug(f"[MQTT] Mensagem publicada (mid: {mid})")
    
    def connect(self) -> bool:
        """Conecta ao broker MQTT"""
        try:
            self.client = mqtt.Client(client_id=self.client_id)
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_publish = self._on_publish
            
            # Conectar ao broker
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            
            # Aguardar conexão
            timeout = 5
            elapsed = 0
            while not self.connected and elapsed < timeout:
                time.sleep(0.1)
                elapsed += 0.1
            
            return self.connected
            
        except Exception as e:
            logger.error(f"Erro ao conectar ao broker MQTT: {e}")
            return False
    
    def disconnect(self):
        """Desconecta do broker MQTT"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
            logger.info("[MQTT] Desconectado do broker")
    
    def publish_temperature(
        self,
        sensor_id: str,
        temperatura: float,
        qos: int = 1,
        retain: bool = False
    ) -> bool:
        """
        Publica dados de temperatura via MQTT
        
        Args:
            sensor_id: ID do sensor
            temperatura: Temperatura medida
            qos: Quality of Service (0, 1, ou 2)
            retain: Se True, mensagem é retida pelo broker
        
        Returns:
            True se publicado com sucesso
        """
        if not self.connected:
            logger.warning("[MQTT] Não conectado - tentando reconectar...")
            if not self.connect():
                return False
        
        try:
            # Extrair sala do sensor_id (ex: salaA-sensor01 -> salaA)
            sala = sensor_id.split('-')[0] if '-' in sensor_id else "unknown"
            
            # Construir tópico: immunotrack/{sala}/{sensor}/temperatura
            topic = f"{self.topic_prefix}/{sala}/{sensor_id}/temperatura"
            
            # Preparar payload
            payload = {
                "sensor_id": sensor_id,
                "temperatura": temperatura,
                "timestamp": datetime.now(timezone(timedelta(hours=-3))).isoformat(),
                "unidade": "celsius"
            }
            
            # Publicar mensagem
            result = self.client.publish(
                topic,
                json.dumps(payload),
                qos=qos,
                retain=retain
            )
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"[MQTT] Publicado: {topic} -> {temperatura}°C (QoS {qos})")
                return True
            else:
                logger.error(f"[MQTT] Falha ao publicar: código {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao publicar temperatura via MQTT: {e}")
            return False
    
    def publish_alert(
        self,
        sensor_id: str,
        temperatura: float,
        tipo_alerta: str,
        mensagem: str,
        qos: int = 2,  # QoS alto para alertas
        retain: bool = True  # Retain para alertas
    ) -> bool:
        """
        Publica alerta via MQTT
        
        Args:
            sensor_id: ID do sensor
            temperatura: Temperatura que gerou o alerta
            tipo_alerta: Tipo do alerta
            mensagem: Mensagem do alerta
            qos: Quality of Service (recomendado 2 para alertas)
            retain: Se True, mensagem é retida pelo broker
        
        Returns:
            True se publicado com sucesso
        """
        if not self.connected:
            if not self.connect():
                return False
        
        try:
            sala = sensor_id.split('-')[0] if '-' in sensor_id else "unknown"
            topic = f"{self.topic_prefix}/{sala}/{sensor_id}/alerta"
            
            payload = {
                "sensor_id": sensor_id,
                "temperatura": temperatura,
                "tipo_alerta": tipo_alerta,
                "mensagem": mensagem,
                "timestamp": datetime.now(timezone(timedelta(hours=-3))).isoformat(),
                "severidade": "CRITICO" if tipo_alerta == "TEMPERATURA_CRITICA" else "ALTO"
            }
            
            result = self.client.publish(
                topic,
                json.dumps(payload),
                qos=qos,
                retain=retain
            )
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.warning(f"[MQTT] Alerta publicado: {topic} -> {mensagem} (QoS {qos})")
                return True
            else:
                logger.error(f"[MQTT] Falha ao publicar alerta: código {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao publicar alerta via MQTT: {e}")
            return False

