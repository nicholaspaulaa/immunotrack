from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

app = FastAPI()

class TemperatureData(BaseModel):
    sensor_id: str
    temperature: float
    timestamp: str

temperature_data = []

@app.get("/")
def root():
    return {"message": "Collector Service"}

@app.post("/api/temperature")
def receive_temperature(data: TemperatureData):
    print(f"Recebido: {data.temperature}°C")
    temperature_data.append(data.dict())
    return {"message": "OK"}

@app.get("/api/temperature/latest")
def get_latest():
    if temperature_data:
        return temperature_data[-1]
    return {"message": "Nenhum dado"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)