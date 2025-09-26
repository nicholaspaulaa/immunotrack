from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import logging
from datetime import datetime, timezone, timedelta
from typing import List
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Serviço Coletor ImmunoTrack",
    description="Serviço que recebe e armazena dados de temperatura dos sensores IoT",
    version="1.0.0"
)

class DadosTemperatura(BaseModel):
    id_sensor: str
    temperatura: float
    timestamp: str

class RespostaSaude(BaseModel):
    status: str
    timestamp: str
    servico: str
    contador_dados: int

class AlertaEmergencia(BaseModel):
    id_alerta: str
    id_sensor: str
    temperatura: float
    tipo_alerta: str
    mensagem: str
    timestamp: str
    severidade: str

dados_temperatura = []

# Lista para armazenar alertas de emergência
alertas_emergencia = []

def notificar_alerta_aws(alerta_dict):
    """Envia notificação via AWS SNS para alertas críticos"""
    try:
        # Verificar se AWS está configurado
        if not os.getenv('AWS_ACCESS_KEY_ID'):
            logger.warning("AWS não configurado - configure suas credenciais no arquivo .env")
            return False
        
        # Importar e usar o sistema de notificações AWS
        import sys
        import os as os_module
        sys.path.append(os_module.path.dirname(os_module.path.dirname(os_module.path.abspath(__file__))))
        from notificacoes_aws import notificar_alerta_critico
        
        notificar_alerta_critico(alerta_dict)
        logger.info("Notificação AWS enviada com sucesso")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao enviar notificação AWS: {e}")
        return False

def criar_alerta_emergencia(id_sensor: str, temperatura: float, tipo_alerta: str, mensagem: str):
    """Cria um alerta de emergência"""
    fuso_brasilia = timezone(timedelta(hours=-3))
    agora_brasilia = datetime.now(fuso_brasilia)
    
    id_alerta = f"ALERTA_{len(alertas_emergencia) + 1}_{agora_brasilia.strftime('%Y%m%d_%H%M%S')}"
    
    # Determinar severidade baseada no tipo de alerta
    if tipo_alerta == "TEMPERATURA_CRITICA":
        severidade = "CRITICO"
    elif tipo_alerta == "SENSOR_OFFLINE":
        severidade = "ALTO"
    else:
        severidade = "MEDIO"
    
    alerta = AlertaEmergencia(
        id_alerta=id_alerta,
        id_sensor=id_sensor,
        temperatura=temperatura,
        tipo_alerta=tipo_alerta,
        mensagem=mensagem,
        timestamp=agora_brasilia.isoformat(),
        severidade=severidade
    )
    
    alertas_emergencia.append(alerta.dict())
    logger.warning(f"ALERTA DE EMERGÊNCIA: {mensagem} - Sensor: {id_sensor} - Temperatura: {temperatura}°C")
    
    # Enviar notificação AWS para alertas críticos
    if severidade == "CRITICO":
        notificar_alerta_aws(alerta.dict())
    
    return alerta

@app.get("/", tags=["Raiz"])
def raiz():
    return {
        "mensagem": "Serviço Coletor ImmunoTrack",
        "versao": "1.0.0",
        "status": "executando",
        "endpoints": {
            "saude": "/saude",
            "ultima_temperatura": "/api/temperatura/ultima",
            "todas_temperaturas": "/api/temperatura/todas",
            "contador_temperatura": "/api/temperatura/contador",
            "painel": "/painel",
            "painel_visual": "/visualizar",
            "documentacao": "/docs",
            "alertas_emergencia": "/api/alertas",
            "ultimo_alerta": "/api/alertas/ultimo",
            "contador_alertas": "/api/alertas/contador",
            "limpar_alertas": "/api/alertas/limpar",
            "simular_emergencia": "/api/alertas/simular"
        }
    }

@app.get("/painel", tags=["Painel"])
def painel():
    contador = len(dados_temperatura)
    ultimo = dados_temperatura[-1] if dados_temperatura else None
    
    return {
        "status_sistema": "ONLINE",
        "total_leituras": contador,
        "ultima_leitura": ultimo,
        "status_sensor": "ATIVO" if contador > 0 else "AGUARDANDO",
        "ultima_atualizacao": datetime.now().isoformat(),
        "faixa_temperatura": "2.0°C - 8.0°C",
        "intervalo_atualizacao": "10 segundos"
    }

@app.get("/saude-pagina", response_class=HTMLResponse, tags=["Visual"])
def pagina_saude():
    """Página amigável para mostrar status do sistema"""
    fuso_brasilia = timezone(timedelta(hours=-3))
    agora_brasilia = datetime.now(fuso_brasilia)
    
    conteudo = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Status do Sistema - ImmunoTrack</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .status {{ color: #27ae60; font-size: 24px; font-weight: bold; }}
            .info {{ margin: 20px 0; padding: 15px; background: #ecf0f1; border-radius: 5px; }}
            .back-btn {{ background: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Status do Sistema ImmunoTrack</h1>
            <div class="status">Sistema Saudável</div>
            <div class="info">
                <strong>Serviço:</strong> Serviço Coletor<br>
                <strong>Status:</strong> Saudável<br>
                <strong>Última Verificação:</strong> {agora_brasilia.strftime('%d/%m/%Y %H:%M:%S')} GMT-3<br>
                <strong>Dados Coletados:</strong> {len(dados_temperatura)} leituras
            </div>
            <a href="/visualizar" class="back-btn">← Voltar ao Dashboard</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=conteudo)

@app.get("/temperaturas-pagina", response_class=HTMLResponse, tags=["Visual"])
def pagina_temperaturas():
    """Página amigável para mostrar todas as temperaturas"""
    conteudo = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Todas as Leituras - ImmunoTrack</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .temp-item {{ margin: 10px 0; padding: 15px; background: #ecf0f1; border-radius: 5px; border-left: 4px solid #3498db; }}
            .temp-value {{ font-size: 18px; font-weight: bold; color: #2c3e50; }}
            .back-btn {{ background: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Todas as Leituras de Temperatura</h1>
            <p><strong>Total de leituras:</strong> {len(dados_temperatura)}</p>
    """
    
    for i, temp in enumerate(dados_temperatura[-10:], 1):  # Mostrar últimas 10
        conteudo += f"""
            <div class="temp-item">
                <div class="temp-value">{temp['temperatura']}°C</div>
                <div><strong>Sensor:</strong> {temp['id_sensor']}</div>
                <div><strong>Horário:</strong> {temp['timestamp']}</div>
            </div>
        """
    
    conteudo += """
            <a href="/visualizar" class="back-btn">← Voltar ao Dashboard</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=conteudo)

@app.get("/alertas-pagina", response_class=HTMLResponse, tags=["Visual"])
def pagina_alertas():
    """Página amigável para mostrar alertas"""
    conteudo = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Alertas de Emergência - ImmunoTrack</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .alert-item {{ margin: 15px 0; padding: 20px; border-radius: 8px; }}
            .alert-critico {{ background: #ffebee; border-left: 5px solid #e74c3c; }}
            .alert-alto {{ background: #fff3e0; border-left: 5px solid #f39c12; }}
            .alert-medio {{ background: #f3e5f5; border-left: 5px solid #9c27b0; }}
            .back-btn {{ background: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Alertas de Emergência</h1>
            <p><strong>Total de alertas:</strong> {len(alertas_emergencia)}</p>
    """
    
    for alerta in alertas_emergencia[-5:]:  # Mostrar últimos 5
        classe = f"alert-{alerta['severidade'].lower()}"
        conteudo += f"""
            <div class="alert-item {classe}">
                <h3>{alerta['tipo_alerta']} - {alerta['severidade']}</h3>
                <p><strong>Sensor:</strong> {alerta['id_sensor']}</p>
                <p><strong>Temperatura:</strong> {alerta['temperatura']}°C</p>
                <p><strong>Mensagem:</strong> {alerta['mensagem']}</p>
                <p><strong>Horário:</strong> {alerta['timestamp']}</p>
            </div>
        """
    
    conteudo += """
            <a href="/visualizar" class="back-btn">← Voltar ao Dashboard</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=conteudo)

@app.get("/simular-emergencia", response_class=HTMLResponse, tags=["Visual"])
def pagina_simular_emergencia():
    """Página para simular emergência"""
    # Simular diferentes tipos de emergência
    tipos_emergencia = [
        ("TEMPERATURA_CRITICA", "Temperatura crítica detectada: 15.5°C - Fora da faixa segura!"),
        ("SENSOR_OFFLINE", "Sensor sensor-001 offline há mais de 5 minutos"),
        ("FALHA_ENERGIA", "Falha de energia detectada no refrigerador"),
        ("PORTA_ABERTA", "Porta do refrigerador aberta há mais de 2 minutos")
    ]
    
    import random
    tipo_alerta, mensagem = random.choice(tipos_emergencia)
    temperatura = random.uniform(10.0, 20.0) if tipo_alerta == "TEMPERATURA_CRITICA" else 0.0
    
    # Criar o alerta
    alerta = criar_alerta_emergencia(
        id_sensor="sensor-001",
        temperatura=temperatura,
        tipo_alerta=tipo_alerta,
        mensagem=mensagem
    )
    
    conteudo = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Simular Emergência - ImmunoTrack</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .success {{ background: #d4edda; border: 1px solid #c3e6cb; color: #155724; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .alert-simulado {{ background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .back-btn {{ background: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 10px; }}
            .simular-btn {{ background: #f39c12; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Simular Emergência</h1>
            
            <div class="success">
                <h3>Alerta de Emergência Simulado com Sucesso!</h3>
                <p>Um novo alerta foi criado para demonstração do sistema.</p>
            </div>
            
            <div class="alert-simulado">
                <h3>🚨 Alerta Simulado:</h3>
                <p><strong>Tipo:</strong> {alerta.tipo_alerta}</p>
                <p><strong>Severidade:</strong> {alerta.severidade}</p>
                <p><strong>Sensor:</strong> {alerta.id_sensor}</p>
                <p><strong>Temperatura:</strong> {alerta.temperatura}°C</p>
                <p><strong>Mensagem:</strong> {alerta.mensagem}</p>
                <p><strong>Horário:</strong> {alerta.timestamp}</p>
            </div>
            
            <div>
                <a href="/visualizar" class="back-btn">← Voltar ao Dashboard</a>
                <a href="/simular-emergencia" class="simular-btn">Simular Outro Alerta</a>
                <a href="/alertas-pagina" class="back-btn">Ver Todos os Alertas</a>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=conteudo)

@app.get("/visualizar", response_class=HTMLResponse, tags=["Visual"])
def painel_visual():
    contador = len(dados_temperatura)
    ultimo = dados_temperatura[-1] if dados_temperatura else None
    
    # Calcular estatísticas
    if dados_temperatura:
        temperaturas = [d['temperatura'] for d in dados_temperatura]
        temp_media = round(sum(temperaturas) / len(temperaturas), 2)
        temp_min = min(temperaturas)
        temp_max = max(temperaturas)
    else:
        temp_media = temp_min = temp_max = 0
    
    # Estatísticas de alertas
    total_alertas = len(alertas_emergencia)
    alertas_criticos = len([a for a in alertas_emergencia if a['severidade'] == 'CRITICO'])
    ultimo_alerta = alertas_emergencia[-1] if alertas_emergencia else None
    
    # Horário GMT-3 (Brasília)
    fuso_brasilia = timezone(timedelta(hours=-3))
    agora_brasilia = datetime.now(fuso_brasilia)
    
    conteudo_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Painel ImmunoTrack</title>
        <meta http-equiv="refresh" content="3">
        <style>
            body {{ 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0; 
                padding: 20px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }}
            .container {{ 
                max-width: 1200px; 
                margin: 0 auto; 
                background: white; 
                padding: 30px; 
                border-radius: 15px; 
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }}
            .header {{ 
                text-align: center; 
                color: #2c3e50; 
                margin-bottom: 40px; 
                border-bottom: 3px solid #3498db;
                padding-bottom: 20px;
            }}
            .status {{ 
                background: linear-gradient(45deg, #27ae60, #2ecc71); 
                color: white; 
                padding: 20px; 
                border-radius: 10px; 
                text-align: center; 
                margin: 20px 0; 
                font-size: 18px;
                font-weight: bold;
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }}
            .data-box {{ 
                background: linear-gradient(135deg, #f8f9fa, #e9ecef); 
                padding: 25px; 
                border-radius: 10px; 
                border-left: 5px solid #3498db;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            .temperature {{ 
                font-size: 48px; 
                color: #e74c3c; 
                font-weight: bold; 
                text-align: center;
                margin: 10px 0;
            }}
            .count {{ 
                font-size: 36px; 
                color: #3498db; 
                font-weight: bold;
                text-align: center;
                margin: 10px 0;
            }}
            .stat-value {{
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                text-align: center;
                margin: 10px 0;
            }}
            .timestamp {{ 
                color: #7f8c8d; 
                font-size: 14px; 
                text-align: center;
                margin-top: 10px;
            }}
            .sensor-info {{
                background: #ecf0f1;
                padding: 15px;
                border-radius: 8px;
                margin: 10px 0;
            }}
            .links {{
                display: flex;
                justify-content: space-around;
                flex-wrap: wrap;
                margin-top: 30px;
            }}
            .link-btn {{
                background: #3498db;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 25px;
                margin: 5px;
                transition: all 0.3s;
            }}
            .link-btn:hover {{
                background: #2980b9;
                transform: translateY(-2px);
            }}
            .alert {{
                background: #fff3cd;
                border: 1px solid #ffeaa7;
                color: #856404;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
            }}
            .emergency-alert {{
                background: linear-gradient(45deg, #e74c3c, #c0392b);
                color: white;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                border-left: 5px solid #c0392b;
                animation: pulse 2s infinite;
            }}
            .alert-critical {{
                background: linear-gradient(45deg, #e74c3c, #c0392b);
                color: white;
            }}
            .alert-high {{
                background: linear-gradient(45deg, #f39c12, #e67e22);
                color: white;
            }}
            .alert-medium {{
                background: linear-gradient(45deg, #f1c40f, #f39c12);
                color: #2c3e50;
            }}
            @keyframes pulse {{
                0% {{ opacity: 1; }}
                50% {{ opacity: 0.7; }}
                100% {{ opacity: 1; }}
            }}
            .alert-counter {{
                background: #e74c3c;
                color: white;
                padding: 5px 10px;
                border-radius: 15px;
                font-size: 12px;
                font-weight: bold;
                margin-left: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Painel ImmunoTrack</h1>
                <p>Sistema de Monitoramento de Temperatura para Vacinas</p>
                <p>Atualizado automaticamente a cada 3 segundos</p>
            </div>
            
            <div class="status">
                <h2>Sistema ONLINE - Monitoramento Ativo
                {f'<span class="alert-counter">{total_alertas} ALERTAS</span>' if total_alertas > 0 else ''}
                </h2>
            </div>
            
            {f'''
            <div class="emergency-alert alert-{ultimo_alerta['severidade'].lower()}">
                <h3>ALERTA DE EMERGÊNCIA - {ultimo_alerta['severidade']}</h3>
                <p><strong>Sensor:</strong> {ultimo_alerta['id_sensor']}</p>
                <p><strong>Temperatura:</strong> {ultimo_alerta['temperatura']}°C</p>
                <p><strong>Mensagem:</strong> {ultimo_alerta['mensagem']}</p>
                <p><strong>Horário:</strong> {ultimo_alerta['timestamp']}</p>
            </div>
            ''' if ultimo_alerta else ''}
            
            <div class="stats-grid">
                <div class="data-box">
                    <h3>Total de Leituras</h3>
                    <div class="count">{contador}</div>
                    <div class="timestamp">Dados coletados</div>
                </div>
                
                <div class="data-box">
                    <h3>Temperatura Atual</h3>
                    {f'''
                    <div class="temperature">{ultimo['temperatura']}°C</div>
                    <div class="sensor-info">
                        <strong>Sensor:</strong> {ultimo['id_sensor']}<br>
                        <strong>Status:</strong> <span style="color: #27ae60;">Normal</span>
                    </div>
                    ''' if ultimo else '''
                    <div class="temperature">--°C</div>
                    <div class="sensor-info">
                        <strong>Status:</strong> <span style="color: #f39c12;">Aguardando dados...</span>
                    </div>
                    '''}
                </div>
                
                <div class="data-box">
                    <h3>Estatísticas</h3>
                    {f'''
                    <div class="stat-value">Média: {temp_media}°C</div>
                    <div class="stat-value">Mín: {temp_min}°C</div>
                    <div class="stat-value">Máx: {temp_max}°C</div>
                    ''' if dados_temperatura else '''
                    <div class="stat-value">Sem dados</div>
                    <div class="stat-value">--</div>
                    <div class="stat-value">--</div>
                    '''}
                </div>
                
                <div class="data-box">
                    <h3>Última Atualização</h3>
                    <div class="stat-value">{agora_brasilia.strftime('%H:%M:%S')} GMT-3</div>
                    <div class="timestamp">{agora_brasilia.strftime('%d/%m/%Y')} - Horário de Brasília</div>
                </div>
                
                <div class="data-box">
                    <h3>Alertas de Emergência</h3>
                    <div class="stat-value" style="color: {'#e74c3c' if alertas_criticos > 0 else '#27ae60'}">
                        {total_alertas} Total
                    </div>
                    <div class="timestamp">
                        {f'{alertas_criticos} Críticos' if alertas_criticos > 0 else 'Sistema Normal'}
                    </div>
                </div>
            </div>
            
            {f'''
            <div class="data-box">
                <h3>Detalhes da Última Leitura</h3>
                <div class="sensor-info">
                    <strong>Temperatura:</strong> {ultimo['temperatura']}°C<br>
                    <strong>ID do Sensor:</strong> {ultimo['id_sensor']}<br>
                    <strong>Timestamp:</strong> {ultimo['timestamp']}<br>
                    <strong>Status:</strong> <span style="color: #27ae60;">Dentro da faixa segura (2°C - 8°C)</span>
                </div>
            </div>
            ''' if ultimo else '''
            <div class="alert">
                <h3>Aguardando Dados do Sensor</h3>
                <p>O sistema está funcionando, mas ainda não recebeu dados dos sensores. Verifique se o sensor está conectado e enviando dados.</p>
            </div>
            '''}
            
            <div class="data-box">
                <h3>Acesso Rápido</h3>
                <div class="links">
                    <a href="/saude-pagina" class="link-btn">Status do Sistema</a>
                    <a href="/temperaturas-pagina" class="link-btn">Todas Leituras</a>
                    <a href="/alertas-pagina" class="link-btn" style="background: {'#e74c3c' if total_alertas > 0 else '#27ae60'}">Alertas ({total_alertas})</a>
                    <a href="/simular-emergencia" class="link-btn" style="background: #f39c12; color: white;">Simular Emergência</a>
                    <a href="/testar-notificacoes" class="link-btn" style="background: #9b59b6; color: white;">📧 Notificações AWS</a>
                </div>
                <div style="margin-top: 15px; font-size: 12px; color: #7f8c8d;">
                    <strong>Status do Sistema:</strong> Verifica se o serviço está funcionando<br>
                    <strong>Todas Leituras:</strong> Lista completa de temperaturas coletadas<br>
                    <strong>Alertas:</strong> Lista de emergências e problemas detectados<br>
                    <strong>Simular Emergência:</strong> Cria um alerta de teste para demonstração<br>
                    <strong>Notificações AWS:</strong> Configura e testa Email para notificações
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=conteudo_html)

@app.get("/saude", response_model=RespostaSaude, tags=["Saude"])
def verificar_saude():
    # Horário GMT-3 (Brasília)
    fuso_brasilia = timezone(timedelta(hours=-3))
    agora_brasilia = datetime.now(fuso_brasilia)
    
    return RespostaSaude(
        status="saudavel",
        timestamp=agora_brasilia.isoformat(),
        servico="servico-coletor",
        contador_dados=len(dados_temperatura)
    )

@app.post("/api/temperatura", tags=["Temperatura"])
def receber_temperatura(dados: DadosTemperatura):
    try:
        # Validar faixa de temperatura para vacinas (2°C - 8°C)
        if dados.temperatura < 2.0 or dados.temperatura > 8.0:
            # Criar alerta de emergência para temperatura crítica
            mensagem_alerta = f"Temperatura crítica detectada: {dados.temperatura}°C - Fora da faixa segura para vacinas!"
            criar_alerta_emergencia(
                id_sensor=dados.id_sensor,
                temperatura=dados.temperatura,
                tipo_alerta="TEMPERATURA_CRITICA",
                mensagem=mensagem_alerta
            )
            
            logger.warning(f"Temperatura fora da faixa segura: {dados.temperatura}°C (sensor: {dados.id_sensor})")
            return {
                "mensagem": "Temperatura fora da faixa segura para vacinas",
                "status": "AVISO",
                "temperatura": dados.temperatura,
                "faixa_segura": "2.0°C - 8.0°C",
                "alerta_criado": True
            }
        
        logger.info(f"Recebido dados do sensor {dados.id_sensor}: {dados.temperatura}°C")
        dados_temperatura.append(dados.dict())
        return {"mensagem": "Dados recebidos com sucesso", "status": "OK"}
    except Exception as e:
        logger.error(f"Erro ao processar dados: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")

@app.get("/api/temperatura/ultima", tags=["Temperatura"])
def obter_ultima():
    if not dados_temperatura:
        return {"mensagem": "Nenhum dado disponível", "dados": None}
    
    ultimo = dados_temperatura[-1]
    logger.info(f"Retornando última leitura: {ultimo['temperatura']}°C")
    return {"mensagem": "Última leitura", "dados": ultimo}

@app.get("/api/temperatura/todas", response_model=List[dict], tags=["Temperatura"])
def obter_todas_temperaturas():
    logger.info(f"Retornando {len(dados_temperatura)} leituras")
    return dados_temperatura

@app.get("/api/temperatura/contador", tags=["Temperatura"])
def obter_contador_dados():
    contador = len(dados_temperatura)
    logger.info(f"Total de leituras: {contador}")
    return {"contador": contador, "mensagem": f"Total de {contador} leituras armazenadas"}

# Endpoints para Sistema de Notificações de Emergência

@app.get("/api/alertas", response_model=List[dict], tags=["Emergencia"])
def obter_todos_alertas():
    """Retorna todos os alertas de emergência"""
    logger.info(f"Retornando {len(alertas_emergencia)} alertas de emergência")
    return alertas_emergencia

@app.get("/api/alertas/ultimo", tags=["Emergencia"])
def obter_ultimo_alerta():
    """Retorna o último alerta de emergência"""
    if not alertas_emergencia:
        return {"mensagem": "Nenhum alerta de emergência", "dados": None}
    
    ultimo = alertas_emergencia[-1]
    logger.info(f"Retornando último alerta: {ultimo['tipo_alerta']}")
    return {"mensagem": "Último alerta", "dados": ultimo}

@app.get("/api/alertas/contador", tags=["Emergencia"])
def obter_contador_alertas():
    """Retorna o número total de alertas de emergência"""
    contador = len(alertas_emergencia)
    contador_criticos = len([a for a in alertas_emergencia if a['severidade'] == 'CRITICO'])
    contador_altos = len([a for a in alertas_emergencia if a['severidade'] == 'ALTO'])
    
    logger.info(f"Total de alertas: {contador} (Críticos: {contador_criticos}, Altos: {contador_altos})")
    return {
        "total_alertas": contador,
        "alertas_criticos": contador_criticos,
        "alertas_altos": contador_altos,
        "alertas_medios": contador - contador_criticos - contador_altos,
        "mensagem": f"Total de {contador} alertas de emergência"
    }

@app.post("/api/alertas/limpar", tags=["Emergencia"])
def limpar_todos_alertas():
    """Limpa todos os alertas de emergência"""
    global alertas_emergencia
    contador_limpos = len(alertas_emergencia)
    alertas_emergencia = []
    logger.info(f"Limpados {contador_limpos} alertas de emergência")
    return {"mensagem": f"Limpados {contador_limpos} alertas de emergência", "status": "OK"}

@app.post("/api/alertas/simular", tags=["Emergencia"])
def simular_emergencia():
    """Simula um alerta de emergência para demonstração"""
    # Simular diferentes tipos de emergência
    tipos_emergencia = [
        ("TEMPERATURA_CRITICA", "Temperatura crítica detectada: 15.5°C - Fora da faixa segura!"),
        ("SENSOR_OFFLINE", "Sensor sensor-001 offline há mais de 5 minutos"),
        ("FALHA_ENERGIA", "Falha de energia detectada no refrigerador"),
        ("PORTA_ABERTA", "Porta do refrigerador aberta há mais de 2 minutos")
    ]
    
    import random
    tipo_alerta, mensagem = random.choice(tipos_emergencia)
    temperatura = random.uniform(10.0, 20.0) if tipo_alerta == "TEMPERATURA_CRITICA" else 0.0
    
    alerta = criar_alerta_emergencia(
        id_sensor="sensor-001",
        temperatura=temperatura,
        tipo_alerta=tipo_alerta,
        mensagem=mensagem
    )
    
    return {
        "mensagem": "Alerta de emergência simulado criado",
        "alerta": alerta.dict(),
        "status": "OK"
    }

@app.get("/testar-notificacoes", response_class=HTMLResponse, tags=["Teste"])
def testar_notificacoes():
    """Página para configurar notificações AWS"""
    # Verificar status AWS
    aws_configurado = bool(os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY'))
    email_configurado = bool(os.getenv('EMAIL_NOTIFICACAO'))
    
    conteudo = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Configurar Notificações AWS - ImmunoTrack</title>
        <meta http-equiv="refresh" content="10">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .status {{ padding: 15px; border-radius: 8px; margin: 20px 0; }}
            .configurado {{ background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }}
            .nao-configurado {{ background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }}
            .btn {{ background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 10px; display: inline-block; }}
            .btn-success {{ background: #28a745; }}
            .btn-warning {{ background: #ffc107; color: #212529; }}
            .btn-danger {{ background: #dc3545; }}
            .config-section {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .step {{ margin: 15px 0; padding: 10px; background: white; border-radius: 5px; border-left: 4px solid #007bff; }}
            .code {{ background: #e9ecef; padding: 10px; border-radius: 5px; font-family: monospace; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📱 Configurar Notificações AWS</h1>
            
            <div class="status {'configurado' if aws_configurado else 'nao-configurado'}">
                <h3>{'AWS Configurado' if aws_configurado else 'AWS Não Configurado'}</h3>
                <p>{'Suas credenciais AWS estão configuradas! Email funcionando.' if aws_configurado else 'Configure suas credenciais AWS para receber notificações por email.'}</p>
            </div>
            
            <div class="config-section">
                <h3>📊 Status da Configuração:</h3>
                <ul>
                    <li><strong>AWS Credentials:</strong> {'Configurado' if aws_configurado else 'Não configurado'}</li>
                    <li><strong>Email:</strong> {'Configurado' if email_configurado else 'Não configurado'}</li>
                </ul>
            </div>
            
            
            <div>
                <a href="/simular-emergencia" class="btn btn-success">Testar Notificação</a>
                <a href="/alertas-pagina" class="btn">Ver Alertas</a>
                <a href="/visualizar" class="btn">Dashboard</a>
            </div>
            
            {f'''
            <div class="config-section">
                <h3>Configuração Atual:</h3>
                <p><strong>Email:</strong> {os.getenv('EMAIL_NOTIFICACAO', 'Não configurado')}</p>
                <p><strong>Região AWS:</strong> {os.getenv('AWS_REGION', 'Não configurado')}</p>
            </div>
            ''' if aws_configurado else ''}
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=conteudo)

if __name__ == "__main__":
    logger.info("Iniciando Serviço Coletor ImmunoTrack...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
