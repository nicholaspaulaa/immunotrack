"""
Subscriber MQTT para coletor
Permite que o coletor receba dados de sensores via MQTT
"""

import paho.mqtt.client as mqtt
import logging
import json
import os
from typing import Callable, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MQTTCollectorSubscriber:
    """Subscreve tópicos MQTT para receber dados de sensores"""
    
    def __init__(
        self,
        broker_host: str = None,
        broker_port: int = 1883,
        client_id: str = None,
        topic_prefix: str = "immunotrack",
        callback_function: Callable = None
    ):
        self.broker_host = broker_host or os.getenv('MQTT_BROKER_HOST', 'mosquitto')
        self.broker_port = int(os.getenv('MQTT_BROKER_PORT', broker_port))
        self.client_id = client_id or f"collector-{os.getpid()}"
        self.topic_prefix = topic_prefix
        self.callback = callback_function
        self.client = None
        self.connected = False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback quando conecta ao broker"""
        if rc == 0:
            self.connected = True
            logger.info(f"[MQTT] Conectado ao broker {self.broker_host}:{self.broker_port}")
            
            temperature_topic = f"{self.topic_prefix}/+/+/temperatura"
            alert_topic = f"{self.topic_prefix}/+/+/alerta"
            
            client.subscribe(temperature_topic, qos=1)
            client.subscribe(alert_topic, qos=2)
            
            logger.info(f"[MQTT] Inscrito nos tópicos: {temperature_topic}, {alert_topic}")
        else:
            self.connected = False
            logger.error(f"[MQTT] Falha ao conectar: código {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback quando desconecta do broker"""
        self.connected = False
        logger.warning(f"[MQTT] Desconectado do broker (código {rc})")
    
    def _on_message(self, client, userdata, msg):
        """Callback quando recebe mensagem"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode('utf-8'))
            
            logger.info(f"[MQTT] Mensagem recebida: {topic}")
            
            # Processar via callback se fornecido
            if self.callback:
                self.callback(topic, payload)
            else:
                logger.warning("[MQTT] Nenhum callback configurado")
                
        except json.JSONDecodeError as e:
            logger.error(f"[MQTT] Erro ao decodificar JSON: {e}")
        except Exception as e:
            logger.error(f"[MQTT] Erro ao processar mensagem: {e}")
    
    def _on_subscribe(self, client, userdata, mid, granted_qos):
        """Callback quando subscreve em um tópico"""
        logger.info(f"[MQTT] Inscrição confirmada (mid: {mid}, QoS: {granted_qos})")
    
    def connect(self) -> bool:
        """Conecta ao broker MQTT e subscreve tópicos"""
        try:
            self.client = mqtt.Client(client_id=self.client_id)
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            self.client.on_subscribe = self._on_subscribe
            
            # Conectar ao broker
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            
            return True
            
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
    
    def subscribe(self, topic: str, qos: int = 1):
        """Subscreve em um tópico adicional"""
        if self.client and self.connected:
            self.client.subscribe(topic, qos=qos)
            logger.info(f"[MQTT] Inscrito no tópico adicional: {topic} (QoS {qos})")
        else:
            logger.warning("[MQTT] Cliente não conectado - não foi possível subscrever")

