#!/usr/bin/env python3
"""
Script de teste para validar o funcionamento do ImmunoTrack
"""

import requests
import time
import json
from datetime import datetime

# Configurações
COLLECTOR_URL = "http://localhost:8000"
TEST_DURATION = 30  # segundos
CHECK_INTERVAL = 5  # segundos

def test_collector_health():
    """Testa se o collector está saudável"""
    print("Testando health do collector...")
    try:
        response = requests.get(f"{COLLECTOR_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"Collector saudável: {data['status']}")
            print(f"   Dados armazenados: {data['data_count']}")
            return True
        else:
            print(f"Health check falhou: {response.status_code}")
            return False
    except Exception as e:
        print(f"Erro no health check: {e}")
        return False

def test_collector_endpoints():
    """Testa todos os endpoints do collector"""
    print("\nTestando endpoints do collector...")
    
    endpoints = [
        ("GET", "/", "Status do serviço"),
        ("GET", "/health", "Health check"),
        ("GET", "/api/temperature/latest", "Última leitura"),
        ("GET", "/api/temperature/all", "Todas as leituras"),
        ("GET", "/api/temperature/count", "Contador de leituras")
    ]
    
    for method, endpoint, description in endpoints:
        try:
            url = f"{COLLECTOR_URL}{endpoint}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                print(f"{description}: OK")
                if endpoint == "/api/temperature/count":
                    data = response.json()
                    print(f"   Total de leituras: {data['count']}")
            else:
                print(f"{description}: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"{description}: Erro - {e}")

def test_data_flow():
    """Testa o fluxo de dados simulando um sensor"""
    print("\nTestando fluxo de dados...")
    
    # Simular dados de temperatura
    test_data = {
        "sensor_id": "test-sensor-001",
        "temperature": 4.5,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # Enviar dados para o collector
        response = requests.post(
            f"{COLLECTOR_URL}/api/temperature",
            json=test_data,
            timeout=10
        )
        
        if response.status_code == 200:
            print("Dados enviados com sucesso")
            
            # Verificar se os dados foram armazenados
            latest_response = requests.get(f"{COLLECTOR_URL}/api/temperature/latest", timeout=5)
            if latest_response.status_code == 200:
                latest_data = latest_response.json()
                if latest_data.get('data', {}).get('sensor_id') == test_data['sensor_id']:
                    print("Dados armazenados e recuperados corretamente")
                    return True
                else:
                    print("Dados não foram armazenados corretamente")
                    return False
            else:
                print("Erro ao recuperar dados")
                return False
        else:
            print(f"Erro ao enviar dados: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Erro no teste de fluxo: {e}")
        return False

def monitor_data_collection():
    """Monitora a coleta de dados por um período"""
    print(f"\nMonitorando coleta de dados por {TEST_DURATION} segundos...")
    
    start_time = time.time()
    initial_count = 0
    
    try:
        # Obter contador inicial
        response = requests.get(f"{COLLECTOR_URL}/api/temperature/count", timeout=5)
        if response.status_code == 200:
            initial_count = response.json()['count']
            print(f"   Leituras iniciais: {initial_count}")
        else:
            print("   Erro ao obter contador inicial")
            return False
        
        # Monitorar por TEST_DURATION segundos
        while time.time() - start_time < TEST_DURATION:
            time.sleep(CHECK_INTERVAL)
            
            try:
                response = requests.get(f"{COLLECTOR_URL}/api/temperature/count", timeout=5)
                if response.status_code == 200:
                    current_count = response.json()['count']
                    new_data = current_count - initial_count
                    print(f"   Novas leituras: {new_data} (total: {current_count})")
                else:
                    print("   Erro ao obter contador")
            except Exception as e:
                print(f"   Erro: {e}")
        
        # Resultado final
        try:
            response = requests.get(f"{COLLECTOR_URL}/api/temperature/count", timeout=5)
            if response.status_code == 200:
                final_count = response.json()['count']
                total_new = final_count - initial_count
                print(f"\nResultado do monitoramento:")
                print(f"   Leituras iniciais: {initial_count}")
                print(f"   Leituras finais: {final_count}")
                print(f"   Novas leituras: {total_new}")
                
                if total_new > 0:
                    print("Sistema está coletando dados ativamente")
                    return True
                else:
                    print("Nenhuma nova leitura detectada")
                    return False
        except Exception as e:
            print(f"Erro no monitoramento: {e}")
            return False
    except Exception as e:
        print(f"Erro no monitoramento: {e}")
        return False

def main():
    """Função principal de teste"""
    print("Iniciando testes do ImmunoTrack")
    print("=" * 50)
    
    # Teste 1: Health check
    if not test_collector_health():
        print("\nCollector não está disponível. Verifique se está rodando.")
        return
    
    # Teste 2: Endpoints
    test_collector_endpoints()
    
    # Teste 3: Fluxo de dados
    if test_data_flow():
        print("Fluxo de dados funcionando")
    else:
        print("Problema no fluxo de dados")
    
    # Teste 4: Monitoramento
    if monitor_data_collection():
        print("Sistema funcionando corretamente")
    else:
        print("Sistema pode ter problemas de coleta")
    
    print("\n" + "=" * 50)
    print("Testes concluídos!")

if __name__ == "__main__":
    main()