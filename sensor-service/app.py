import requests
import time
import random
from datetime import datetime

def send_temperature(sensor_id, collector_url):
    temperature = round(random.uniform(2.0, 8.0), 2)
    payload = {
        "sensor_id": sensor_id,
        "temperature": temperature,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(f"{collector_url}/api/temperature", json=payload)
        if response.status_code == 200:
            print(f"Enviado: {temperature}°C")
        else:
            print(f"Erro: {response.status_code}")
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    sensor_id = "sensor-001"
    collector_url = "http://localhost:8000"
    
    while True:
        send_temperature(sensor_id, collector_url)
        time.sleep(10)