from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import logging
from datetime import datetime
from typing import List

# Configurando os logs para acompanhar o que está acontecendo
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criando nossa API principal
app = FastAPI(
    title="ImmunoTrack Collector Service",
    description="Serviço que recebe e armazena dados de temperatura dos sensores IoT",
    version="1.0.0"
)

# Modelo para os dados de temperatura que recebemos dos sensores
class TemperatureData(BaseModel):
    sensor_id: str
    temperature: float
    timestamp: str

# Modelo para resposta do health check
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    service: str
    data_count: int

# Lista para armazenar os dados (por enquanto em memória, depois vamos usar DynamoDB)
temperature_data = []

# Página inicial - mostra que o serviço está funcionando
@app.get("/", tags=["Root"])
def root():
    """Página inicial do serviço"""
    return {
        "message": "ImmunoTrack Collector Service",
        "version": "1.0.0",
        "status": "running"
    }

# Endpoint para verificar se o serviço está saudável
@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    """Verifica se o serviço está funcionando corretamente"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        service="collector-service",
        data_count=len(temperature_data)
    )

# Endpoint para receber dados dos sensores
@app.post("/api/temperature", tags=["Temperature"])
def receive_temperature(data: TemperatureData):
    """Recebe dados de temperatura enviados pelos sensores"""
    try:
        logger.info(f"Recebido dados do sensor {data.sensor_id}: {data.temperature}°C")
        temperature_data.append(data.dict())
        return {"message": "Dados recebidos com sucesso", "status": "OK"}
    except Exception as e:
        logger.error(f"Erro ao processar dados: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")

# Endpoint para pegar a última leitura de temperatura
@app.get("/api/temperature/latest", tags=["Temperature"])
def get_latest():
    """Retorna a temperatura mais recente que recebemos"""
    if not temperature_data:
        return {"message": "Nenhum dado disponível", "data": None}
    
    latest = temperature_data[-1]
    logger.info(f"Retornando última leitura: {latest['temperature']}°C")
    return {"message": "Última leitura", "data": latest}

# Endpoint para pegar todas as leituras de temperatura
@app.get("/api/temperature/all", response_model=List[dict], tags=["Temperature"])
def get_all_temperatures():
    """Retorna todas as temperaturas que já recebemos"""
    logger.info(f"Retornando {len(temperature_data)} leituras")
    return temperature_data

# Endpoint para saber quantas leituras temos
@app.get("/api/temperature/count", tags=["Temperature"])
def get_data_count():
    """Mostra quantas leituras de temperatura já recebemos"""
    count = len(temperature_data)
    logger.info(f"Total de leituras: {count}")
    return {"count": count, "message": f"Total de {count} leituras armazenadas"}

# Aqui é onde tudo começa quando executamos o arquivo
if __name__ == "__main__":
    logger.info("Iniciando ImmunoTrack Collector Service...")
    uvicorn.run(app, host="0.0.0.0", port=8000)