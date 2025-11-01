import requests
import time
import random
import logging
import os
from datetime import datetime, timezone, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import MQTT opcional
try:
    from mqtt_publisher import MQTTSensorPublisher
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    logger.warning("[MQTT] Módulo mqtt_publisher não disponível - usando HTTP apenas")

class SensorTemperatura:
    def __init__(self, id_sensor: str, url_coletor: str, intervalo: int = 10, use_mqtt: bool = False):
        self.id_sensor = id_sensor
        self.url_coletor = url_coletor
        self.intervalo = intervalo
        self.contador_tentativas = 0
        self.max_tentativas = 3
        self.use_mqtt = use_mqtt and MQTT_AVAILABLE
        self.mqtt_publisher = None
        
        # Inicializar MQTT se habilitado
        if self.use_mqtt:
            try:
                self.mqtt_publisher = MQTTSensorPublisher()
                if self.mqtt_publisher.connect():
                    logger.info("[MQTT] Conectado ao broker MQTT")
                else:
                    logger.warning("[MQTT] Falha ao conectar - usando HTTP como fallback")
                    self.use_mqtt = False
            except Exception as e:
                logger.error(f"[MQTT] Erro ao inicializar MQTT: {e}")
                self.use_mqtt = False
        
    def gerar_temperatura(self) -> float:
        # Gerar apenas temperaturas normais (2°C - 8°C)
        # Alertas críticos são gerados apenas manualmente via botão no site
        return round(random.uniform(2.0, 8.0), 2)
    
    def verificar_saude_coletor(self) -> bool:
        """Verifica saúde do coletor com retry automático"""
        max_tentativas = 5
        tentativa = 0
        
        while tentativa < max_tentativas:
            try:
                response = requests.get(f"{self.url_coletor}/saude", timeout=10)
                if response.status_code == 200:
                    dados_saude = response.json()
                    logger.info(f"Status do coletor: {dados_saude['status']}")
                    return True
                else:
                    logger.warning(f"Coletor respondeu com código {response.status_code}")
                    tentativa += 1
                    if tentativa < max_tentativas:
                        time.sleep(3)
            except requests.exceptions.Timeout:
                tentativa += 1
                if tentativa < max_tentativas:
                    logger.warning(f"Timeout ao conectar (tentativa {tentativa}/{max_tentativas}) - aguardando...")
                    time.sleep(5)
                else:
                    logger.error(f"Timeout após {max_tentativas} tentativas")
            except requests.exceptions.ConnectionError as e:
                tentativa += 1
                if tentativa < max_tentativas:
                    logger.warning(f"Erro de conexão (tentativa {tentativa}/{max_tentativas}): {e} - aguardando...")
                    time.sleep(5)
                else:
                    logger.error(f"Erro de conexão após {max_tentativas} tentativas: {e}")
            except Exception as e:
                logger.error(f"Erro ao verificar saúde do coletor: {e}")
                tentativa += 1
                if tentativa < max_tentativas:
                    time.sleep(3)
        
        return False
    
    def enviar_temperatura(self) -> bool:
        temperatura = self.gerar_temperatura()
        # Horário GMT-3 (Brasília)
        fuso_brasilia = timezone(timedelta(hours=-3))
        agora_brasilia = datetime.now(fuso_brasilia)
        
        # Temperatura sempre normal (2°C - 8°C)
        # Alertas críticos são gerados apenas manualmente via botão no site
        
        # Usar MQTT se habilitado
        if self.use_mqtt and self.mqtt_publisher:
            try:
                sucesso = self.mqtt_publisher.publish_temperature(
                    sensor_id=self.id_sensor,
                    temperatura=temperatura,
                    qos=1
                )
                if sucesso:
                    logger.info(f"[MQTT] Dados enviados: {temperatura}°C")
                    self.contador_tentativas = 0
                    return True
                else:
                    logger.warning("[MQTT] Falha ao publicar - tentando HTTP como fallback")
                    # Fallback para HTTP se MQTT falhar
            except Exception as e:
                logger.error(f"[MQTT] Erro ao publicar: {e} - tentando HTTP como fallback")
        
        # Usar HTTP REST (padrão ou fallback)
        payload = {
            "id_sensor": self.id_sensor,
            "temperatura": temperatura,
            "timestamp": agora_brasilia.isoformat()
        }
        
        try:
            response = requests.post(
                f"{self.url_coletor}/api/temperatura", 
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"[HTTP] Dados enviados: {temperatura}°C")
                self.contador_tentativas = 0
                return True
            else:
                logger.error(f"Erro HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Erro: {e}")
            return False
    
    def executar_com_tentativas(self):
        sucesso = self.enviar_temperatura()
        
        if not sucesso:
            self.contador_tentativas += 1
            if self.contador_tentativas <= self.max_tentativas:
                logger.warning(f"Tentativa {self.contador_tentativas}/{self.max_tentativas}")
                time.sleep(5)
                return self.executar_com_tentativas()
            else:
                logger.error(f"Máximo de tentativas excedido")
                self.contador_tentativas = 0
    
    def iniciar(self):
        logger.info(f"Iniciando sensor {self.id_sensor}")
        logger.info(f"Conectando com coletor: {self.url_coletor}")
        
        # Tentar conectar com retry automático
        if not self.verificar_saude_coletor():
            logger.error("Coletor não está disponível após várias tentativas")
            logger.info("Sensor continuará tentando enviar dados mesmo sem confirmação inicial...")
        else:
            logger.info(f"Coletor conectado! Enviando dados a cada {self.intervalo} segundos")
        
        # Continuar mesmo se não conseguir verificar saúde inicialmente
        # O próprio envio tentará reconectar
        while True:
            self.executar_com_tentativas()
            time.sleep(self.intervalo)

if __name__ == "__main__":
    ID_SENSOR = os.getenv("SENSOR_ID", "sensor-001")
    URL_COLETOR = os.getenv("COLLECTOR_URL", "http://collector-service:80")
    INTERVALO = int(os.getenv("INTERVAL", "10"))
    USE_MQTT = os.getenv("USE_MQTT", "false").lower() == "true"
    
    sensor = SensorTemperatura(ID_SENSOR, URL_COLETOR, INTERVALO, use_mqtt=USE_MQTT)
    sensor.iniciar()
