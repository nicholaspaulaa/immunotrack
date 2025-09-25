import requests
import time
import random
import logging
import os
from datetime import datetime, timezone, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SensorTemperatura:
    def __init__(self, id_sensor: str, url_coletor: str, intervalo: int = 10):
        self.id_sensor = id_sensor
        self.url_coletor = url_coletor
        self.intervalo = intervalo
        self.contador_tentativas = 0
        self.max_tentativas = 3
        
    def gerar_temperatura(self) -> float:
        # Gerar apenas temperaturas normais (2°C - 8°C)
        # Alertas críticos são gerados apenas manualmente via botão no site
        return round(random.uniform(2.0, 8.0), 2)
    
    def verificar_saude_coletor(self) -> bool:
        try:
            response = requests.get(f"{self.url_coletor}/saude", timeout=5)
            if response.status_code == 200:
                dados_saude = response.json()
                logger.info(f"Status do coletor: {dados_saude['status']}")
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao verificar saúde do coletor: {e}")
            return False
    
    def enviar_temperatura(self) -> bool:
        temperatura = self.gerar_temperatura()
        # Horário GMT-3 (Brasília)
        fuso_brasilia = timezone(timedelta(hours=-3))
        agora_brasilia = datetime.now(fuso_brasilia)
        
        # Temperatura sempre normal (2°C - 8°C)
        # Alertas críticos são gerados apenas manualmente via botão no site
        
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
                logger.info(f"Dados enviados: {temperatura}°C")
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
        
        if not self.verificar_saude_coletor():
            logger.error("Coletor não está disponível")
            return
        
        logger.info(f"Coletor conectado! Enviando dados a cada {self.intervalo} segundos")
        
        while True:
            self.executar_com_tentativas()
            time.sleep(self.intervalo)

if __name__ == "__main__":
    ID_SENSOR = "sensor-001"
    URL_COLETOR = os.getenv("COLLECTOR_URL", "http://collector-service:8000")
    INTERVALO = int(os.getenv("INTERVAL", "10"))
    
    sensor = SensorTemperatura(ID_SENSOR, URL_COLETOR, INTERVALO)
    sensor.iniciar()
