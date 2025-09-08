# Sistema de Controle de Temperatura

## Serviços

### 1. Sensor Service
- Simula sensor de temperatura
- Envia dados via POST para Collector

### 2. Collector Service  
- Recebe dados dos sensores
- Armazena em memória

## API

- `POST /api/temperature` - Recebe dados do sensor
- `GET /api/temperature/latest` - Última temperatura

