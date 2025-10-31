from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import logging
from datetime import datetime, timezone, timedelta
from typing import List
import os
from dotenv import load_dotenv
import asyncio
import socket

from dynamodb_basic import DynamoDBService
from notificacoes_aws import notificar_alerta_critico

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

# Lista para armazenar alertas de emergência (mantida para compatibilidade visual)
alertas_emergencia = []

# DynamoDB e liderança
db_service = None
owner_id = socket.gethostname()
is_lider_atual = False
LEASE_TTL_SECONDS = int(os.getenv('LEADER_TTL_SECONDS', '20'))

async def _loop_eleicao_lider():
    global is_lider_atual
    # Jitter inicial
    await asyncio.sleep(1)
    while True:
        try:
            if not is_lider_atual:
                conquistou = db_service.adquirir_lease_lider(owner_id, LEASE_TTL_SECONDS)
                is_lider_atual = conquistou
                if is_lider_atual:
                    logger.info(f"[LIDERANCA] Instância {owner_id} virou LÍDER")
            else:
                renovou = db_service.renovar_lease_lider(owner_id, LEASE_TTL_SECONDS)
                if not renovou:
                    logger.warning("[LIDERANCA] Perdi a liderança")
                    is_lider_atual = False
        except Exception as e:
            logger.error(f"[LIDERANCA] Erro no loop de eleição: {e}")
        # Pequeno jitter para evitar sincronização
        await asyncio.sleep(max(5, LEASE_TTL_SECONDS // 2))

@app.on_event("startup")
async def on_startup():
    global db_service
    db_service = DynamoDBService()
    asyncio.create_task(_loop_eleicao_lider())

def notificar_alerta_aws(alerta_dict):
    """Envia notificação via AWS SNS para alertas críticos"""
    try:
        # Verificar se AWS está configurado
        if not os.getenv('AWS_ACCESS_KEY_ID'):
            logger.warning("AWS não configurado - configure suas credenciais no arquivo .env")
            return False

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
    
    # Garantir que o alerta tenha o campo 'id' para compatibilidade
    alerta_dict = alerta.dict()
    alerta_dict['id'] = alerta_dict.get('id_alerta', id_alerta)
    alertas_emergencia.append(alerta_dict)
    logger.warning(f"ALERTA DE EMERGÊNCIA: {mensagem} - Sensor: {id_sensor} - Temperatura: {temperatura}°C")

    # Persistir no DynamoDB
    try:
        if db_service:
            salvo = db_service.salvar_alerta(
                id_sensor=id_sensor,
                temperatura=temperatura,
                tipo_alerta=tipo_alerta,
                mensagem=mensagem,
                severidade=severidade
            )
            # Atualiza id_alerta com id persistido (usado para mutex de notificação)
            alerta.id_alerta = salvo.get('id', alerta.id_alerta)
            # Atualiza o alerta_dict com o id persistido
            if salvo.get('id'):
                alerta_dict['id'] = salvo.get('id')
                alerta_dict['id_alerta'] = salvo.get('id')
                # Atualiza o último item da lista (que acabamos de adicionar)
                if alertas_emergencia:
                    alertas_emergencia[-1] = alerta_dict
    except Exception as e:
        logger.error(f"Erro ao salvar alerta no DynamoDB: {e}")

    # Enviar notificação AWS para alertas críticos somente se líder e send-once
    if severidade == "CRITICO":
        try:
            if db_service and is_lider_atual:
                if db_service.marcar_alerta_notificado_uma_vez(alerta.id_alerta):
                    notificar_alerta_aws(alerta.dict())
                else:
                    logger.info("Notificação já enviada por outra instância")
            elif is_lider_atual:
                # Sem DB (fallback): envia mesmo assim
                notificar_alerta_aws(alerta.dict())
        except Exception as e:
            logger.error(f"Erro ao processar notificação crítica: {e}")
    
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
    # Preferir dados do DB
    ultimo = db_service.obter_ultima_temperatura() if db_service else (dados_temperatura[-1] if dados_temperatura else None)
    contador = (db_service.contar_temperaturas() if db_service else len(dados_temperatura))
    
    return {
        "status_sistema": "ONLINE",
        "total_leituras": contador,
        "ultima_leitura": ultimo,
        "status_sensor": "ATIVO" if contador > 0 else "AGUARDANDO",
        "ultima_atualizacao": datetime.now().isoformat(),
        "faixa_temperatura": "2.0°C - 8.0°C",
        "intervalo_atualizacao": "10 segundos",
        "lider": is_lider_atual,
        "owner_id": owner_id
    }

@app.get("/saude-pagina", response_class=HTMLResponse, tags=["Visual"])
def pagina_saude():
    """Página amigável para mostrar status do sistema"""
    fuso_brasilia = timezone(timedelta(hours=-3))
    agora_brasilia = datetime.now(fuso_brasilia)
    
    # Construir HTML dos cartões dos sensores sem f-strings aninhadas
    sensor_blocks = []
    for sid in sensores_alvo:
        item = leituras.get(sid)
        temp_line = (
            f"<div class='kv'><span>Temperatura</span><span>{item['temperatura']}°C</span></div>"
            if item else "<div class='kv'><span>Temperatura</span><span>--</span></div>"
        )
        last_line = (
            f"<div class='kv'><span>Último</span><span>{item['timestamp']}</span></div>"
            if item else "<div class='kv'><span>Último</span><span>Sem dados</span></div>"
        )
        block = (
            "<div class='card'>"
            f"<div class='title'>{sid}</div>"
            f"{temp_line}"
            f"{last_line}"
            f"<div class='links'><a class='btn' href='/visualizar?sensor={sid}'>Ver detalhes</a></div>"
            "</div>"
        )
        sensor_blocks.append(block)
    sensor_html = ''.join(sensor_blocks)

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
    import random
    # Escolher aleatoriamente um dos 3 sensores disponíveis
    sensores_disponiveis = ["salaA-sensor01", "salaB-sensor02", "salaC-sensor03"]
    sensor_aleatorio = random.choice(sensores_disponiveis)
    
    # Simular diferentes tipos de emergência
    tipos_emergencia = [
        ("TEMPERATURA_CRITICA", f"Temperatura crítica detectada: 15.5°C - Fora da faixa segura!"),
        ("SENSOR_OFFLINE", f"Sensor {sensor_aleatorio} offline há mais de 5 minutos"),
        ("FALHA_ENERGIA", f"Falha de energia detectada no refrigerador - {sensor_aleatorio}"),
        ("PORTA_ABERTA", f"Porta do refrigerador aberta há mais de 2 minutos - {sensor_aleatorio}")
    ]
    
    tipo_alerta, mensagem = random.choice(tipos_emergencia)
    temperatura = random.uniform(10.0, 20.0) if tipo_alerta == "TEMPERATURA_CRITICA" else 0.0
    
    # Criar o alerta
    alerta = criar_alerta_emergencia(
        id_sensor=sensor_aleatorio,
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
def painel_visual(request: Request):
    # Usar contador do DynamoDB para ter o total correto
    contador = db_service.contar_temperaturas() if db_service else len(dados_temperatura)
    ultimo = dados_temperatura[-1] if dados_temperatura else None
    
    # Calcular estatísticas - buscar mais dados para garantir que temos os últimos de cada sensor
    dados_origem = (db_service.obter_todas_temperaturas(limite=500) if db_service else dados_temperatura)
    if dados_origem:
        temperaturas = [d['temperatura'] for d in dados_origem]
        temp_media = round(sum(temperaturas) / len(temperaturas), 2)
        temp_min = min(temperaturas)
        temp_max = max(temperaturas)
    else:
        temp_media = temp_min = temp_max = 0
    
    # Estatísticas de alertas (filtrar alertas resolvidos)
    alertas_origem = (db_service.obter_todos_alertas(limite=50) if db_service else alertas_emergencia)
    alertas_nao_resolvidos = [a for a in alertas_origem if not a.get('resolvido', False)]
    total_alertas = len(alertas_nao_resolvidos)
    alertas_criticos = len([a for a in alertas_nao_resolvidos if a['severidade'] == 'CRITICO'])
    ultimo_alerta = alertas_nao_resolvidos[0] if alertas_nao_resolvidos else None
    
    # Extrair ID do alerta para uso no HTML (escapar aspas simples para JavaScript)
    id_alerta_html = ''
    if ultimo_alerta:
        id_raw = ultimo_alerta.get('id') or ultimo_alerta.get('id_alerta') or ''
        # Escapar aspas simples para uso em JavaScript
        id_alerta_html = id_raw.replace("'", "\\'").replace('"', '\\"') if id_raw else ''
    
    # Horário GMT-3 (Brasília)
    fuso_brasilia = timezone(timedelta(hours=-3))
    agora_brasilia = datetime.now(fuso_brasilia)

    # Sensores ativos (contagem e última leitura por id_sensor)
    sensores_contagem = {}
    sensores_ultima = {}
    sensores_ultima_formatado = {}
    if dados_origem:
        for d in dados_origem:
            sid = d.get('id_sensor', 'desconhecido')
            sensores_contagem[sid] = sensores_contagem.get(sid, 0) + 1
            ts = d.get('timestamp') or d.get('data_criacao', '')
            if sid not in sensores_ultima or (ts and ts > sensores_ultima[sid]):
                sensores_ultima[sid] = ts
                # Formatar timestamp para exibição legível
                try:
                    if 'T' in ts:
                        dt_obj = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    else:
                        dt_obj = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
                    sensores_ultima_formatado[sid] = dt_obj.strftime('%d/%m/%Y %H:%M:%S')
                except:
                    sensores_ultima_formatado[sid] = ts

    # Filtro por sensor via query param ?sensor=<id>
    sensor_selecionado = request.query_params.get('sensor')
    if sensor_selecionado:
        dados_origem = [d for d in dados_origem if d.get('id_sensor') == sensor_selecionado]
        # recalc stats com filtro
        if dados_origem:
            temperaturas = [d['temperatura'] for d in dados_origem]
            temp_media = round(sum(temperaturas) / len(temperaturas), 2)
            temp_min = min(temperaturas)
            temp_max = max(temperaturas)
        else:
            temp_media = temp_min = temp_max = 0
    # definir 'ultimo' com base em dados_origem (após possível filtro)
    if dados_origem:
        try:
            # se vier do DB já está ordenado; ainda assim garantimos o mais recente
            ultimo = sorted(dados_origem, key=lambda x: x.get('data_criacao', x.get('timestamp', '')), reverse=True)[0]
        except Exception:
            ultimo = dados_origem[0]

    # Buscar alertas do banco para associar aos gráficos (apenas não resolvidos)
    alertas_por_sensor = {}
    try:
        if db_service:
            todos_alertas = db_service.obter_todos_alertas(limite=200)
            # Filtrar apenas alertas não resolvidos
            alertas_nao_resolvidos = [a for a in todos_alertas if not a.get('resolvido', False)]
            for alerta in alertas_nao_resolvidos:
                sensor_id_alert = alerta.get('id_sensor', '')
                if sensor_id_alert not in alertas_por_sensor:
                    alertas_por_sensor[sensor_id_alert] = []
                # Armazenar temperatura e timestamp do alerta para matching
                ts_alerta = alerta.get('timestamp') or alerta.get('data_criacao', '')
                alertas_por_sensor[sensor_id_alert].append({
                    'temperatura': float(alerta.get('temperatura', 0)),
                    'timestamp': ts_alerta,
                    'tipo': alerta.get('tipo_alerta', '')
                })
        else:
            # Modo memória: usar alertas_emergencia (filtrados não resolvidos)
            for alerta in alertas_emergencia:
                if alerta.get('resolvido', False):
                    continue
                sensor_id_alert = alerta.get('id_sensor', '')
                if sensor_id_alert not in alertas_por_sensor:
                    alertas_por_sensor[sensor_id_alert] = []
                ts_alerta = alerta.get('timestamp') or alerta.get('data_criacao', '')
                alertas_por_sensor[sensor_id_alert].append({
                    'temperatura': float(alerta.get('temperatura', 0)),
                    'timestamp': ts_alerta,
                    'tipo': alerta.get('tipo_alerta', '')
                })
    except Exception as e:
        logger.error(f"Erro ao buscar alertas para gráficos: {e}")
        alertas_por_sensor = {}

    # Série para gráficos temporais: um gráfico por sensor (últimas 15 leituras por sensor)
    graficos_por_sensor = {}
    sensores_filtrados_grafico = [sid for sid in sensores_contagem.keys() if sid != 'sensor-001']
    
    try:
        if dados_origem:
            # Agrupar leituras por sensor
            for sensor_id in sensores_filtrados_grafico:
                leituras_sensor = [d for d in dados_origem if d.get('id_sensor') == sensor_id]
                
                # Criar lista combinada de leituras e alertas
                dados_combinados = []
                
                # Adicionar leituras normais
                for leitura in leituras_sensor:
                    ts_str = leitura.get('timestamp') or leitura.get('data_criacao', '')
                    try:
                        if 'T' in ts_str:
                            dt_obj = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                        else:
                            dt_obj = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                    except:
                        dt_obj = datetime.now()
                    
                    dados_combinados.append({
                        'temperatura': float(leitura.get('temperatura', 0)),
                        'timestamp': dt_obj,
                        'tipo': 'leitura',
                        'tem_alerta': False
                    })
                
                # Adicionar alertas como leituras no gráfico
                if sensor_id in alertas_por_sensor:
                    for alerta in alertas_por_sensor[sensor_id]:
                        ts_str = alerta.get('timestamp', '')
                        try:
                            if ts_str:
                                if 'T' in ts_str:
                                    dt_obj = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                                else:
                                    dt_obj = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                            else:
                                dt_obj = datetime.now()
                        except:
                            dt_obj = datetime.now()
                        
                        dados_combinados.append({
                            'temperatura': float(alerta.get('temperatura', 0)),
                            'timestamp': dt_obj,
                            'tipo': 'alerta',
                            'tem_alerta': True
                        })
                
                if dados_combinados:
                    # Ordenar por timestamp
                    dados_combinados.sort(key=lambda x: x['timestamp'])
                    # Pegar últimas 15 (leituras + alertas combinados)
                    rec = dados_combinados[-15:] if len(dados_combinados) > 15 else dados_combinados
                    
                    dados_temp = []
                    timestamps_temp = []
                    tem_alerta = []  # Lista de booleanos indicando se cada ponto tem alerta
                    
                    for item in rec:
                        dados_temp.append(item['temperatura'])
                        timestamps_temp.append(item['timestamp'].strftime('%H:%M'))
                        # Marcar como alerta se for um alerta ou se estiver fora da faixa
                        fora_faixa = item['temperatura'] < 2.0 or item['temperatura'] > 8.0
                        tem_alerta.append(item['tem_alerta'] or fora_faixa)
                    
                    # Calcular estatísticas com os últimos dados (mesmos do gráfico)
                    if dados_temp:
                        temp_max_total = max(dados_temp)
                        temp_min_total = min(dados_temp)
                        temp_media_total = round(sum(dados_temp) / len(dados_temp), 2)
                        temp_ultima_total = dados_temp[-1]
                    else:
                        temp_max_total = temp_min_total = temp_media_total = temp_ultima_total = 0
                    
                    # Sempre armazenar estatísticas (mesmo com menos de 2 pontos)
                    graficos_por_sensor[sensor_id] = {
                        'dados': dados_temp,
                        'timestamps': timestamps_temp,
                        'tem_alerta': tem_alerta,  # Indica quais pontos têm alerta
                        'estatisticas': {
                            'max': temp_max_total,
                            'min': temp_min_total,
                            'media': temp_media_total,
                            'ultima': temp_ultima_total
                        }
                    }
    except Exception:
        graficos_por_sensor = {}

    # Função auxiliar para gerar SVG de um gráfico
    def gerar_svg_grafico(dados, timestamps, sensor_id, tem_alerta_lista=None):
        if len(dados) < 2:
            return ''
        if tem_alerta_lista is None:
            tem_alerta_lista = [False] * len(dados)
        
        # Dimensões (menor para múltiplos gráficos)
        w = 450
        h = 180
        pad_x = 50
        pad_y_top = 20
        pad_y_bottom = 35
        area_h = h - pad_y_top - pad_y_bottom
        
        # Calcular limites Y
        temp_min_val = min(dados) if dados else 0
        temp_max_val = max(dados) if dados else 10
        if temp_min_val == temp_max_val:
            temp_min_val -= 2
            temp_max_val += 2
        y_min = min(0, temp_min_val - 1)
        y_max = max(10, temp_max_val + 1)
        y_range = y_max - y_min
        
        def y_for_temp(v):
            return pad_y_top + int((1 - (v - y_min) / y_range) * area_h)
        
        # Posições X
        n_pts = len(dados)
        xs = []
        if n_pts == 1:
            xs = [w // 2]
        else:
            for i in range(n_pts):
                xs.append(pad_x + int((w - 2 * pad_x) * i / (n_pts - 1)))
        
        # Pontos da linha completa (para manter linha contínua)
        pontos_linha_completa = ' '.join([f"{xs[i]},{y_for_temp(dados[i])}" for i in range(n_pts)])
        
        # Área da faixa segura (2-8°C)
        y_segura_min = y_for_temp(2.0)
        y_segura_max = y_for_temp(8.0)
        area_segura_path = f"M {pad_x},{y_segura_max} L {w - pad_x},{y_segura_max} L {w - pad_x},{y_segura_min} L {pad_x},{y_segura_min} Z"
        
        # Linha de referência (5°C)
        y_ref = y_for_temp(5.0)
        
        # Labels eixo Y
        y_labels = []
        y_steps = 4
        for i in range(y_steps + 1):
            val_y = y_min + (y_max - y_min) * i / y_steps
            y_pos = y_for_temp(val_y)
            y_labels.append(f'<text x="8" y="{y_pos + 4}" font-size="9" fill="#7f8c8d">{val_y:.1f}°C</text>')
        
        # Labels eixo X (apenas início e fim)
        x_labels = []
        if n_pts > 0:
            x_labels.append(f'<text x="{xs[0]}" y="{h - 8}" font-size="8" fill="#7f8c8d" text-anchor="middle">{timestamps[0]}</text>')
            if n_pts > 1:
                x_labels.append(f'<text x="{xs[-1]}" y="{h - 8}" font-size="8" fill="#7f8c8d" text-anchor="middle">{timestamps[-1]}</text>')
        
        # Gerar pontos normais e pontos com alerta (vermelho)
        pontos_circulos = []
        for i in range(n_pts):
            x = xs[i]
            y = y_for_temp(dados[i])
            if tem_alerta_lista[i]:
                # Ponto com alerta - vermelho e maior
                pontos_circulos.append(f"<circle cx='{x}' cy='{y}' r='5' fill='#e74c3c' stroke='white' stroke-width='2' />")
            else:
                pontos_circulos.append(f"<circle cx='{x}' cy='{y}' r='3.5' fill='#3498db' stroke='white' stroke-width='1.5' />")
        
        return f"""
                    <svg viewBox='0 0 {w} {h}' width='100%' height='{h}px' preserveAspectRatio='xMidYMid meet' style='background:#fafafa; border-radius:8px; box-shadow: 0 2px 6px rgba(0,0,0,0.06);'>
                        <title>{sensor_id}</title>
                        <!-- Área da faixa segura -->
                        <path d='{area_segura_path}' fill='#d5f4e6' opacity='0.5' />
                        <!-- Linha de referência (5°C) -->
                        <line x1='{pad_x}' y1='{y_ref}' x2='{w - pad_x}' y2='{y_ref}' stroke='#27ae60' stroke-width='1' stroke-dasharray='3,3' opacity='0.5' />
                        <!-- Linha principal (contínua) -->
                        <polyline fill='none' stroke='#3498db' stroke-width='2.5' points='{pontos_linha_completa}' />
                        <!-- Pontos normais e com alerta -->
                        {''.join(pontos_circulos)}
                        <!-- Labels -->
                        {''.join(y_labels)}
                        {''.join(x_labels)}
                        <!-- Grade -->
                        {''.join([f"<line x1='{pad_x}' y1='{y_for_temp(y_min + (y_max - y_min) * i / y_steps)}' x2='{w - pad_x}' y2='{y_for_temp(y_min + (y_max - y_min) * i / y_steps)}' stroke='#ecf0f1' stroke-width='1' />" for i in range(y_steps + 1)])}
                    </svg>
"""
    
    # Gerar HTML de todos os gráficos por sensor
    graficos_html_lista = []
    for sensor_id in sorted(sensores_filtrados_grafico):
        if sensor_id in graficos_por_sensor:
            dados_sensor = graficos_por_sensor[sensor_id]['dados']
            tem_alerta_lista = graficos_por_sensor[sensor_id].get('tem_alerta', [False] * len(dados_sensor))
            svg = gerar_svg_grafico(
                dados_sensor,
                graficos_por_sensor[sensor_id]['timestamps'],
                sensor_id,
                tem_alerta_lista
            )
            if svg:
                # Usar estatísticas calculadas com TODOS os dados do sensor
                stats = graficos_por_sensor[sensor_id].get('estatisticas', {})
                temp_max = stats.get('max', 0)
                temp_min = stats.get('min', 0)
                temp_media = stats.get('media', 0)
                temp_ultima = stats.get('ultima', 0)
                
                sensor_id_safe = sensor_id.replace('-', '_').replace(' ', '_')
                graficos_html_lista.append(f"""
                    <div id="grafico_{sensor_id_safe}" style='margin-bottom: 20px; padding: 16px; background: #fafafa; border-radius: 8px;'>
                        <h4 style='margin-bottom: 12px; color: #2c3e50; font-size: 16px; font-weight: bold;'>{sensor_id}</h4>
                        <div style='display: flex; gap: 16px; align-items: stretch;'>
                            <div id="svg_{sensor_id_safe}" style='flex: 1; display: flex; align-items: center;'>
                                {svg}
                            </div>
                            <div id="stats_{sensor_id_safe}" style='width: 180px; padding: 12px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); display: flex; flex-direction: column; justify-content: space-between;'>
                                <div style='font-size: 12px; color: #7f8c8d; margin-bottom: 12px; font-weight: bold;'>Estatísticas</div>
                                <div style='margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #ecf0f1;'>
                                    <div style='font-size: 11px; color: #95a5a6; margin-bottom: 4px;'>Máxima</div>
                                    <div id="max_{sensor_id_safe}" style='font-size: 18px; font-weight: bold; color: #e74c3c;'>{temp_max:.1f}°C</div>
                                </div>
                                <div style='margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #ecf0f1;'>
                                    <div style='font-size: 11px; color: #95a5a6; margin-bottom: 4px;'>Média</div>
                                    <div id="media_{sensor_id_safe}" style='font-size: 18px; font-weight: bold; color: #3498db;'>{temp_media:.1f}°C</div>
                                </div>
                                <div style='margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #ecf0f1;'>
                                    <div style='font-size: 11px; color: #95a5a6; margin-bottom: 4px;'>Mínima</div>
                                    <div id="min_{sensor_id_safe}" style='font-size: 18px; font-weight: bold; color: #2ecc71;'>{temp_min:.1f}°C</div>
                                </div>
                                <div>
                                    <div style='font-size: 11px; color: #95a5a6; margin-bottom: 4px;'>Última</div>
                                    <div id="ultima_{sensor_id_safe}" style='font-size: 18px; font-weight: bold; color: #2c3e50;'>{temp_ultima:.1f}°C</div>
                                </div>
                            </div>
                        </div>
                    </div>
""")
    # Construir HTML dos gráficos por sensor
    grafico_html = ''
    if graficos_html_lista:
        grafico_html = ''.join(graficos_html_lista)
    elif not dados_origem:
        grafico_html = """
                    <div class="stat-value" style="text-align:center; padding:20px;">Aguardando dados dos sensores</div>
"""
    else:
        grafico_html = """
                    <div class="stat-value" style="text-align:center; padding:20px;">Sem dados suficientes para gráfico (mínimo 2 leituras por sensor)</div>
"""

    # Construir HTML dos sensores ativos separadamente para evitar conflito de aspas
    sensores_html = ''
    sensores_filtrados = [(sid, qtd) for sid, qtd in sorted(sensores_contagem.items()) if sid != 'sensor-001']
    if sensores_filtrados:
        sensores_cards = []
        for sid, qtd in sensores_filtrados:
            ultima_formatada = sensores_ultima_formatado.get(sid, 'Sem dados')
            sensores_cards.append(f"""
                    <div style='margin-bottom: 16px; padding: 14px; background: #f8f9fa; border-radius: 8px;'>
                        <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;'>
                            <strong style='color: #2c3e50; font-size: 16px;'>{sid}</strong>
                            <span style='background: #3498db; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold;'>{qtd} leituras</span>
                        </div>
                        <div style='color: #7f8c8d; font-size: 13px;'>
                            <span style='color: #95a5a6;'>Última leitura:</span> <strong style='color: #34495e;'>{ultima_formatada}</strong>
                        </div>
                    </div>
""")
        sensores_html = ''.join(sensores_cards)
    else:
        sensores_html = '<div style="text-align: center; padding: 20px; color: #95a5a6;">Nenhum sensor ativo</div>'

    # Replicação (contadores principal vs réplica, quando disponível)
    contador_temperaturas = 0
    contador_temperaturas_replica = None
    contador_alertas = total_alertas
    contador_alertas_replica = None
    replica_status = 'não habilitada'
    replica_last_update = '-'
    try:
        contador_temperaturas = db_service.contar_temperaturas() if db_service else len(dados_temperatura)
    except Exception:
        pass
    try:
        if db_service and hasattr(db_service, 'dynamodb'):
            t_rep = db_service.dynamodb.Table('immunotrack-temperaturas-replica')
            r = t_rep.scan(Select='COUNT')
            contador_temperaturas_replica = r.get('Count', 0)
            # buscar última atualização simples
            r_full = t_rep.scan(Limit=1000)
            items_rep = r_full.get('Items', [])
            if items_rep:
                # ordenar por data_criacao quando disponível
                try:
                    items_rep.sort(key=lambda x: x.get('data_criacao', ''), reverse=True)
                    replica_last_update = items_rep[0].get('data_criacao', '-')
                except Exception:
                    replica_last_update = '-'
    except Exception:
        contador_temperaturas_replica = None
    try:
        if db_service and hasattr(db_service, 'dynamodb'):
            a_rep = db_service.dynamodb.Table('immunotrack-alertas-replica')
            r2 = a_rep.scan(Select='COUNT')
            contador_alertas_replica = r2.get('Count', 0)
    except Exception:
        contador_alertas_replica = None
    # Determinar status replicação
    if contador_temperaturas_replica is not None and contador_alertas_replica is not None:
        ok_temp = (contador_temperaturas_replica == contador_temperaturas)
        ok_alert = (contador_alertas_replica == contador_alertas)
        if ok_temp and ok_alert:
            replica_status = 'em dia'
        else:
            replica_status = 'atraso'
    
    conteudo_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Painel ImmunoTrack</title>
        <!-- Atualização automática via JavaScript (sem reload da página) -->
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
            .leader-badge {{ display: inline-block; background: #2ecc71; color: white; padding: 6px 12px; border-radius: 16px; font-size: 12px; margin-left: 10px; }}
            .card-title {{ font-weight: bold; color: #2c3e50; margin-bottom: 10px; }}
            .kv {{ display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #ecf0f1; }}
            .kv:last-child {{ border-bottom: none; }}
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
                position: relative;
            }}
            .btn-resolver {{
                position: absolute;
                top: 12px;
                right: 12px;
                background: #27ae60;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                cursor: pointer;
                transition: all 0.3s;
            }}
            .btn-resolver:hover {{
                background: #2ecc71;
                transform: scale(1.05);
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
            /* Badges */
            .badge {{ display: inline-block; padding: 6px 12px; border-radius: 14px; font-size: 12px; font-weight: bold; margin-left: 10px; }}
            .badge-online {{ background: #27ae60; color: #fff; }}
            /* Centralização do filtro de sensores */
            .sensor-filter {{ text-align: center; }}
            .sensor-filter h3 {{ text-align: center; margin-bottom: 8px; }}
            .sensor-filter form {{ display: inline-block; }}
            .sensor-filter select {{
                margin: 10px auto;
                min-width: 260px;
                padding: 10px 40px 10px 14px;
                border: 2px solid #e1e5e9;
                border-radius: 24px;
                background: #ffffff;
                box-shadow: 0 4px 10px rgba(0,0,0,0.06);
                font-size: 14px;
                color: #2c3e50;
                transition: all 0.2s ease;
                appearance: none;
                -moz-appearance: none;
                -webkit-appearance: none;
                background-image:
                    url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="%233498db" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>');
                background-repeat: no-repeat;
                background-position: right 14px center;
                background-size: 16px 16px;
            }}
            .sensor-filter select:hover {{
                box-shadow: 0 6px 14px rgba(0,0,0,0.08);
                border-color: #cfd6dc;
            }}
            .sensor-filter select:focus {{
                outline: none;
                border-color: #3498db;
                box-shadow: 0 0 0 4px rgba(52,152,219,0.15);
            }}
            /* Espaçamento entre containers principais */
            .data-box.spacing-top {{
                margin-top: 30px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                    <h1>
                    Painel ImmunoTrack
                    <span id="sensores-online-badge" class="badge badge-online">Sensores online: {len(sensores_contagem)}</span>
                </h1>
                <p>Sistema de Monitoramento de Temperatura para Vacinas</p>
            </div>

            <div class="data-box sensor-filter">
                <h3>Selecionar Sensor</h3>
                <form method="get" action="/visualizar">
                    <select name="sensor" onchange="this.form.submit()">
                        <option value="">Todos os sensores</option>
                        {''.join([f'<option value="{sid}" '+('selected' if sensor_selecionado==sid else '')+f'>{sid}</option>' for sid in sorted([k for k in sensores_contagem.keys() if k != 'sensor-001'])])}
                    </select>
                </form>
                <div class="timestamp">{('Filtrando por: ' + sensor_selecionado) if sensor_selecionado else 'Sem filtro de sensor'}</div>
            </div>
            
            <div class="status">
                <h2>Sistema ONLINE - Monitoramento Ativo
                {f'<span id="alert-counter-badge" class="alert-counter">{total_alertas} ALERTAS</span>' if total_alertas > 0 else '<span id="alert-counter-badge" class="alert-counter" style="display:none;"></span>'}
                </h2>
                <p id="ultima-atualizacao">Última atualização: {agora_brasilia.strftime('%d/%m/%Y %H:%M:%S')} GMT-3</p>
            </div>
            
            {f''' 
            <div class="emergency-alert alert-{ultimo_alerta['severidade'].lower()}">
                <button class="btn-resolver" onclick="resolverAlerta('{id_alerta_html}')">Marcar como resolvido</button>
                <h3>ALERTA DE EMERGÊNCIA - {ultimo_alerta['severidade']}</h3>
                <p><strong>Sensor:</strong> {ultimo_alerta['id_sensor']}</p>
                <p><strong>Temperatura:</strong> {ultimo_alerta['temperatura']}°C</p>
                <p><strong>Mensagem:</strong> {ultimo_alerta['mensagem']}</p>
                <p><strong>Horário:</strong> {ultimo_alerta['timestamp']}</p>
            </div>
            ''' if ultimo_alerta and not ultimo_alerta.get('resolvido', False) and id_alerta_html else ''}
            
            <div class="stats-grid">
                <div class="data-box">
                    <h3>Temperatura Atual</h3>
                    {f''' 
                    <div id="temperatura-atual" class="temperature">{ultimo['temperatura']}°C</div>
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
                
                

                {f'''
                <div class="data-box">
                    <div class="card-title">Replicação (demo)</div>
                    <div class="kv"><span>Temperaturas (primário)</span><span>{contador_temperaturas}</span></div>
                    <div class="kv"><span>Temperaturas (réplica)</span><span>{contador_temperaturas_replica}</span></div>
                    <div class="kv"><span>Alertas (primário)</span><span>{total_alertas}</span></div>
                    <div class="kv"><span>Alertas (réplica)</span><span>{contador_alertas_replica}</span></div>
                    <div class="kv"><span>Status</span><span>{replica_status}</span></div>
                    <div class="timestamp">Última atualização réplica: {replica_last_update}</div>
                </div>
                ''' if contador_temperaturas_replica is not None and contador_alertas_replica is not None else ''}

                <div class="data-box">
                    <h3>Estatísticas</h3>
                    {sensores_html if sensores_html else '<div class="stat-value" style="text-align:center; padding:20px;">Aguardando dados dos sensores</div>'}
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
            <div class="data-box spacing-top">
                <div class="card-title">Gráfico de Temperatura</div>
                {grafico_html}
            </div>

            <div class="data-box spacing-top">
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
            
            <div class="data-box spacing-top">
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
        <script>
            function resolverAlerta(alertaId) {{
                console.log('Função resolverAlerta chamada com ID:', alertaId, 'Tipo:', typeof alertaId);
                
                // Validar e limpar o ID
                if (!alertaId) {{
                    console.error('ID do alerta é null ou undefined');
                    alert('Erro: ID do alerta não encontrado. Recarregue a página.');
                    return;
                }}
                
                // Converter para string e remover espaços
                alertaId = String(alertaId).trim();
                
                if (alertaId === 'undefined' || alertaId === '' || alertaId === 'null') {{
                    console.error('ID do alerta inválido após processamento:', alertaId);
                    alert('Erro: ID do alerta inválido. Recarregue a página.');
                    return;
                }}
                
                if (!confirm('Deseja marcar este alerta como resolvido?')) {{
                    return;
                }}
                
                console.log('Enviando requisição para resolver alerta:', alertaId);
                const url = `/api/alertas/${{encodeURIComponent(alertaId)}}/resolver`;
                console.log('URL da requisição:', url);
                
                fetch(url, {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }}
                }})
                .then(response => {{
                    console.log('Status da resposta:', response.status, response.statusText);
                    console.log('Headers da resposta:', response.headers);
                    
                    if (!response.ok) {{
                        // Tentar ler o JSON mesmo em caso de erro
                        return response.json().then(errData => {{
                            console.error('Erro retornado pelo servidor:', errData);
                            throw new Error(errData.mensagem || `HTTP error! status: ${{response.status}}`);
                        }}).catch(parseError => {{
                            console.error('Erro ao parsear JSON de erro:', parseError);
                            throw new Error(`HTTP error! status: ${{response.status}} - ${{response.statusText}}`);
                        }});
                    }}
                    return response.json();
                }})
                .then(data => {{
                    console.log('Resposta completa do servidor:', JSON.stringify(data, null, 2));
                    if (data.status === 'OK') {{
                        alert('Alerta marcado como resolvido!');
                        location.reload();
                    }} else {{
                        console.error('Erro na resposta:', data);
                        alert('Erro ao resolver alerta: ' + (data.mensagem || 'Erro desconhecido'));
                    }}
                }})
                .catch(error => {{
                    console.error('Erro completo ao resolver alerta:');
                    console.error('Mensagem:', error.message);
                    console.error('Stack:', error.stack);
                    console.error('ID do alerta tentado:', alertaId);
                    console.error('Tipo do erro:', error.name);
                    alert('Erro ao resolver alerta: ' + error.message + '\\n\\nVerifique o console do navegador (F12) para mais detalhes.');
                }});
            }}
            
            // Função para gerar SVG do gráfico (versão JavaScript)
            function gerarSVGGrafico(dados, timestamps, sensorId, temAlertaLista) {{
                if (dados.length < 2) return '';
                
                const w = 450;
                const h = 180;
                const pad_x = 50;
                const pad_y_top = 20;
                const pad_y_bottom = 35;
                const area_h = h - pad_y_top - pad_y_bottom;
                
                const temp_min_val = Math.min(...dados);
                const temp_max_val = Math.max(...dados);
                const y_min = Math.min(0, temp_min_val - 1);
                const y_max = Math.max(10, temp_max_val + 1);
                const y_range = y_max - y_min;
                
                function yForTemp(v) {{
                    return pad_y_top + Math.floor((1 - (v - y_min) / y_range) * area_h);
                }}
                
                const n_pts = dados.length;
                const xs = [];
                if (n_pts === 1) {{
                    xs.push(w / 2);
                }} else {{
                    for (let i = 0; i < n_pts; i++) {{
                        xs.push(pad_x + Math.floor((w - 2 * pad_x) * i / (n_pts - 1)));
                    }}
                }}
                
                const pontos_linha = xs.map((x, i) => `${{x}},${{yForTemp(dados[i])}}`).join(' ');
                
                const y_segura_min = yForTemp(2.0);
                const y_segura_max = yForTemp(8.0);
                const area_segura_path = `M ${{pad_x}},${{y_segura_max}} L ${{w - pad_x}},${{y_segura_max}} L ${{w - pad_x}},${{y_segura_min}} L ${{pad_x}},${{y_segura_min}} Z`;
                
                const y_ref = yForTemp(5.0);
                
                const pontos_circulos = xs.map((x, i) => {{
                    const y = yForTemp(dados[i]);
                    if (temAlertaLista && temAlertaLista[i]) {{
                        return `<circle cx='${{x}}' cy='${{y}}' r='5' fill='#e74c3c' stroke='white' stroke-width='2' />`;
                    }} else {{
                        return `<circle cx='${{x}}' cy='${{y}}' r='3.5' fill='#3498db' stroke='white' stroke-width='1.5' />`;
                    }}
                }}).join('');
                
                const y_labels = [];
                const y_steps = 4;
                for (let i = 0; i <= y_steps; i++) {{
                    const val_y = y_min + (y_max - y_min) * i / y_steps;
                    const y_pos = yForTemp(val_y);
                    y_labels.push(`<text x="8" y="${{y_pos + 4}}" font-size="9" fill="#7f8c8d">${{val_y.toFixed(1)}}°C</text>`);
                }}
                
                const x_labels = [];
                if (n_pts > 0) {{
                    x_labels.push(`<text x="${{xs[0]}}" y="${{h - 8}}" font-size="8" fill="#7f8c8d" text-anchor="middle">${{timestamps[0]}}</text>`);
                    if (n_pts > 1) {{
                        x_labels.push(`<text x="${{xs[n_pts - 1]}}" y="${{h - 8}}" font-size="8" fill="#7f8c8d" text-anchor="middle">${{timestamps[n_pts - 1]}}</text>`);
                    }}
                }}
                
                const grade_lines = [];
                for (let i = 0; i <= y_steps; i++) {{
                    const y_pos = yForTemp(y_min + (y_max - y_min) * i / y_steps);
                    grade_lines.push(`<line x1='${{pad_x}}' y1='${{y_pos}}' x2='${{w - pad_x}}' y2='${{y_pos}}' stroke='#ecf0f1' stroke-width='1' />`);
                }}
                
                return `<svg viewBox='0 0 ${{w}} ${{h}}' width='100%' height='${{h}}px' preserveAspectRatio='xMidYMid meet' style='background:#fafafa; border-radius:8px; box-shadow: 0 2px 6px rgba(0,0,0,0.06);'>
                    <title>${{sensorId}}</title>
                    <path d='${{area_segura_path}}' fill='#d5f4e6' opacity='0.5' />
                    <line x1='${{pad_x}}' y1='${{y_ref}}' x2='${{w - pad_x}}' y2='${{y_ref}}' stroke='#27ae60' stroke-width='1' stroke-dasharray='3,3' opacity='0.5' />
                    <polyline fill='none' stroke='#3498db' stroke-width='2.5' points='${{pontos_linha}}' />
                    ${{pontos_circulos}}
                    ${{y_labels.join('')}}
                    ${{x_labels.join('')}}
                    ${{grade_lines.join('')}}
                </svg>`;
            }}
            
            // Função para atualizar gráficos e dados da página
            function atualizarGraficos() {{
                console.log('[Atualização] Buscando dados...', new Date().toLocaleTimeString());
                fetch('/api/graficos/dados')
                    .then(response => {{
                        if (!response.ok) {{
                            throw new Error(`HTTP error! status: ${{response.status}}`);
                        }}
                        return response.json();
                    }})
                    .then(data => {{
                        console.log('[Atualização] Dados recebidos:', data);
                        if (data.erro) {{
                            console.error('Erro ao buscar dados:', data.erro);
                            return;
                        }}
                        
                        // Atualizar temperatura atual
                        const tempAtualEl = document.getElementById('temperatura-atual');
                        if (tempAtualEl && data.temperatura_atual) {{
                            tempAtualEl.textContent = `${{data.temperatura_atual.toFixed(1)}}°C`;
                        }}
                        
                        // Atualizar contador de alertas
                        const alertBadge = document.getElementById('alert-counter-badge');
                        if (alertBadge) {{
                            if (data.total_alertas > 0) {{
                                alertBadge.textContent = `${{data.total_alertas}} ALERTAS`;
                                alertBadge.style.display = 'inline';
                            }} else {{
                                alertBadge.textContent = '';
                                alertBadge.style.display = 'none';
                            }}
                        }}
                        
                        // Atualizar sensores online
                        const sensoresBadge = document.getElementById('sensores-online-badge');
                        if (sensoresBadge) {{
                            sensoresBadge.textContent = `Sensores online: ${{data.sensores_ativos || 0}}`;
                        }}
                        
                        // Atualizar última atualização
                        const ultimaAtualizacaoEl = document.getElementById('ultima-atualizacao');
                        if (ultimaAtualizacaoEl && data.timestamp_formatado) {{
                            ultimaAtualizacaoEl.textContent = `Última atualização: ${{data.timestamp_formatado}} GMT-3`;
                        }}
                        
                        // Atualizar gráficos
                        const graficos = data.graficos || {{}};
                        
                        for (const sensorId in graficos) {{
                            const sensorData = graficos[sensorId];
                            const sensorIdSafe = sensorId.replace(/-/g, '_').replace(/ /g, '_');
                            
                            // Atualizar SVG
                            const svgContainer = document.getElementById(`svg_${{sensorIdSafe}}`);
                            if (svgContainer && sensorData.dados && sensorData.dados.length >= 2) {{
                                const svg = gerarSVGGrafico(
                                    sensorData.dados,
                                    sensorData.timestamps || [],
                                    sensorId,
                                    sensorData.tem_alerta || []
                                );
                                svgContainer.innerHTML = svg;
                            }}
                            
                            // Atualizar estatísticas
                            const stats = sensorData.estatisticas || {{}};
                            const maxEl = document.getElementById(`max_${{sensorIdSafe}}`);
                            const mediaEl = document.getElementById(`media_${{sensorIdSafe}}`);
                            const minEl = document.getElementById(`min_${{sensorIdSafe}}`);
                            const ultimaEl = document.getElementById(`ultima_${{sensorIdSafe}}`);
                            
                            if (maxEl) maxEl.textContent = `${{stats.max ? stats.max.toFixed(1) : '0.0'}}°C`;
                            if (mediaEl) mediaEl.textContent = `${{stats.media ? stats.media.toFixed(1) : '0.0'}}°C`;
                            if (minEl) minEl.textContent = `${{stats.min ? stats.min.toFixed(1) : '0.0'}}°C`;
                            if (ultimaEl) ultimaEl.textContent = `${{stats.ultima ? stats.ultima.toFixed(1) : '0.0'}}°C`;
                        }}
                        
                        console.log('[Atualização] Dados atualizados com sucesso');
                    }})
                    .catch(error => {{
                        console.error('[Atualização] Erro ao atualizar dados:', error);
                    }});
            }}
            
            // Sincronização: Tudo atualiza a cada 3 segundos
            // - Sensores geram dados a cada 3 segundos
            // - Dashboard atualiza gráficos e estatísticas a cada 3 segundos
            const INTERVALO_ATUALIZACAO = 3000; // 3 segundos (sincronizado com sensores)
            
            console.log(`[Sincronização] Configurando atualização automática a cada ${{INTERVALO_ATUALIZACAO/1000}} segundos`);
            setInterval(atualizarGraficos, INTERVALO_ATUALIZACAO);
            
            // Atualizar após um pequeno delay para garantir que os dados iniciais estejam disponíveis
            console.log('[Sincronização] Primeira atualização após 1 segundo');
            setTimeout(() => {{
                atualizarGraficos();
            }}, 1000);
        </script>
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
        servico=("servico-coletor-lider" if is_lider_atual else "servico-coletor-seguidor"),
        contador_dados=(db_service.contar_temperaturas() if db_service else len(dados_temperatura))
    )

@app.post("/api/temperatura", tags=["Temperatura"])
def receber_temperatura(dados: DadosTemperatura):
    try:
        # SEMPRE salvar a leitura, independente de estar dentro ou fora da faixa
        logger.info(f"Recebido dados do sensor {dados.id_sensor}: {dados.temperatura}°C")
        dados_temperatura.append(dados.dict())
        # Persistir no DynamoDB
        if db_service:
            try:
                db_service.salvar_temperatura(dados.id_sensor, dados.temperatura, dados.timestamp)
            except Exception as e:
                logger.error(f"Erro ao salvar temperatura no DynamoDB: {e}")
        
        # Validar faixa de temperatura para vacinas (2°C - 8°C) e criar alerta se necessário
        alerta_criado = False
        if dados.temperatura < 2.0 or dados.temperatura > 8.0:
            # Criar alerta de emergência para temperatura crítica
            mensagem_alerta = f"Temperatura crítica detectada: {dados.temperatura}°C - Fora da faixa segura para vacinas!"
            criar_alerta_emergencia(
                id_sensor=dados.id_sensor,
                temperatura=dados.temperatura,
                tipo_alerta="TEMPERATURA_CRITICA",
                mensagem=mensagem_alerta
            )
            alerta_criado = True
            logger.warning(f"Temperatura fora da faixa segura: {dados.temperatura}°C (sensor: {dados.id_sensor})")
            return {
                "mensagem": "Dados recebidos e alerta criado",
                "status": "AVISO",
                "temperatura": dados.temperatura,
                "faixa_segura": "2.0°C - 8.0°C",
                "alerta_criado": True
            }
        
        return {"mensagem": "Dados recebidos com sucesso", "status": "OK"}
    except Exception as e:
        logger.error(f"Erro ao processar dados: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")

@app.get("/api/temperatura/ultima", tags=["Temperatura"])
def obter_ultima():
    if db_service:
        ultimo = db_service.obter_ultima_temperatura()
        if not ultimo:
            return {"mensagem": "Nenhum dado disponível", "dados": None}
    else:
        if not dados_temperatura:
            return {"mensagem": "Nenhum dado disponível", "dados": None}
        ultimo = dados_temperatura[-1]
    logger.info(f"Retornando última leitura: {ultimo['temperatura']}°C")
    return {"mensagem": "Última leitura", "dados": ultimo}

@app.get("/api/temperatura/todas", response_model=List[dict], tags=["Temperatura"])
def obter_todas_temperaturas():
    if db_service:
        dados = db_service.obter_todas_temperaturas(limite=100)
        logger.info(f"Retornando {len(dados)} leituras (DB)")
        return dados
    logger.info(f"Retornando {len(dados_temperatura)} leituras (mem)")
    return dados_temperatura

@app.get("/api/temperatura/contador", tags=["Temperatura"])
def obter_contador_dados():
    contador = db_service.contar_temperaturas() if db_service else len(dados_temperatura)
    logger.info(f"Total de leituras: {contador}")
    return {"contador": contador, "mensagem": f"Total de {contador} leituras armazenadas"}

@app.get("/api/graficos/dados", tags=["Graficos"])
def obter_dados_graficos():
    """Retorna os dados necessários para atualizar os gráficos"""
    try:
        # Buscar dados
        dados_origem = (db_service.obter_todas_temperaturas(limite=500) if db_service else dados_temperatura)
        
        # Buscar alertas não resolvidos
        alertas_origem = (db_service.obter_todos_alertas(limite=200) if db_service else alertas_emergencia)
        alertas_nao_resolvidos = [a for a in alertas_origem if not a.get('resolvido', False)]
        
        # Agrupar alertas por sensor
        alertas_por_sensor = {}
        for alerta in alertas_nao_resolvidos:
            sensor_id_alert = alerta.get('id_sensor', '')
            if sensor_id_alert not in alertas_por_sensor:
                alertas_por_sensor[sensor_id_alert] = []
            ts_alerta = alerta.get('timestamp') or alerta.get('data_criacao', '')
            alertas_por_sensor[sensor_id_alert].append({
                'temperatura': float(alerta.get('temperatura', 0)),
                'timestamp': ts_alerta,
                'tipo': alerta.get('tipo_alerta', '')
            })
        
        # Processar dados por sensor
        graficos_dados = {}
        sensores_contagem = {}
        if dados_origem:
            for d in dados_origem:
                sid = d.get('id_sensor', 'desconhecido')
                sensores_contagem[sid] = sensores_contagem.get(sid, 0) + 1
        
        sensores_filtrados = [sid for sid in sensores_contagem.keys() if sid != 'sensor-001']
        
        for sensor_id in sensores_filtrados:
            leituras_sensor = [d for d in dados_origem if d.get('id_sensor') == sensor_id]
            
            # Criar lista combinada de leituras e alertas
            dados_combinados = []
            
            # Adicionar leituras normais
            for leitura in leituras_sensor:
                ts_str = leitura.get('timestamp') or leitura.get('data_criacao', '')
                try:
                    if 'T' in ts_str:
                        dt_obj = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    else:
                        dt_obj = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                except:
                    dt_obj = datetime.now()
                
                dados_combinados.append({
                    'temperatura': float(leitura.get('temperatura', 0)),
                    'timestamp': dt_obj,
                    'tipo': 'leitura',
                    'tem_alerta': False
                })
            
            # Adicionar alertas como leituras no gráfico
            if sensor_id in alertas_por_sensor:
                for alerta in alertas_por_sensor[sensor_id]:
                    ts_str = alerta.get('timestamp', '')
                    try:
                        if ts_str:
                            if 'T' in ts_str:
                                dt_obj = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                            else:
                                dt_obj = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                        else:
                            dt_obj = datetime.now()
                    except:
                        dt_obj = datetime.now()
                    
                    dados_combinados.append({
                        'temperatura': float(alerta.get('temperatura', 0)),
                        'timestamp': dt_obj,
                        'tipo': 'alerta',
                        'tem_alerta': True
                    })
            
            if dados_combinados:
                # Ordenar por timestamp
                dados_combinados.sort(key=lambda x: x['timestamp'])
                # Pegar últimas 15 (leituras + alertas combinados)
                rec = dados_combinados[-15:] if len(dados_combinados) > 15 else dados_combinados
                
                dados_temp = []
                timestamps_temp = []
                tem_alerta = []
                
                for item in rec:
                    dados_temp.append(item['temperatura'])
                    timestamps_temp.append(item['timestamp'].strftime('%H:%M'))
                    # Marcar como alerta se for um alerta ou se estiver fora da faixa
                    fora_faixa = item['temperatura'] < 2.0 or item['temperatura'] > 8.0
                    tem_alerta.append(item['tem_alerta'] or fora_faixa)
                
                # Calcular estatísticas
                if dados_temp:
                    temp_max = max(dados_temp)
                    temp_min = min(dados_temp)
                    temp_media = round(sum(dados_temp) / len(dados_temp), 2)
                    temp_ultima = dados_temp[-1]
                else:
                    temp_max = temp_min = temp_media = temp_ultima = 0
                
                graficos_dados[sensor_id] = {
                    'dados': dados_temp,
                    'timestamps': timestamps_temp,
                    'tem_alerta': tem_alerta,
                    'estatisticas': {
                        'max': temp_max,
                        'min': temp_min,
                        'media': temp_media,
                        'ultima': temp_ultima
                    }
                }
        
        # Buscar última temperatura e contador
        ultimo_temp = None
        contador_total = 0
        try:
            if db_service:
                ultimo_temp = db_service.obter_ultima_temperatura()
                contador_total = db_service.contar_temperaturas()
            else:
                if dados_temperatura:
                    ultimo_temp = dados_temperatura[-1]
                contador_total = len(dados_temperatura)
        except Exception:
            pass
        
        # Buscar alertas não resolvidos
        total_alertas = len(alertas_nao_resolvidos)
        
        # Contar sensores ativos
        sensores_ativos = len(sensores_filtrados)
        
        agora_brasilia = datetime.now(timezone(timedelta(hours=-3)))
        
        # Converter temperatura_atual para float se necessário
        temp_atual_float = 0
        if ultimo_temp:
            temp_val = ultimo_temp.get('temperatura', 0)
            if isinstance(temp_val, (int, float)):
                temp_atual_float = float(temp_val)
            else:
                try:
                    temp_atual_float = float(str(temp_val))
                except:
                    temp_atual_float = 0
        
        return {
            "graficos": graficos_dados,
            "temperatura_atual": temp_atual_float,
            "sensor_atual": ultimo_temp.get('id_sensor', '') if ultimo_temp else '',
            "contador_total": contador_total,
            "total_alertas": total_alertas,
            "sensores_ativos": sensores_ativos,
            "timestamp": agora_brasilia.isoformat(),
            "timestamp_formatado": agora_brasilia.strftime('%d/%m/%Y %H:%M:%S')
        }
    except Exception as e:
        logger.error(f"Erro ao obter dados dos gráficos: {e}", exc_info=True)
        return {"graficos": {}, "erro": str(e)}

# Endpoints para Sistema de Notificações de Emergência

@app.get("/api/alertas", response_model=List[dict], tags=["Emergencia"])
def obter_todos_alertas():
    """Retorna todos os alertas de emergência"""
    if db_service:
        dados = db_service.obter_todos_alertas(limite=100)
        logger.info(f"Retornando {len(dados)} alertas de emergência (DB)")
        return dados
    logger.info(f"Retornando {len(alertas_emergencia)} alertas de emergência (mem)")
    return alertas_emergencia

@app.get("/api/alertas/ultimo", tags=["Emergencia"])
def obter_ultimo_alerta():
    """Retorna o último alerta de emergência"""
    if db_service:
        ultimo = db_service.obter_ultimo_alerta()
        if not ultimo:
            return {"mensagem": "Nenhum alerta de emergência", "dados": None}
    else:
        if not alertas_emergencia:
            return {"mensagem": "Nenhum alerta de emergência", "dados": None}
        ultimo = alertas_emergencia[-1]
    logger.info(f"Retornando último alerta: {ultimo['tipo_alerta']}")
    return {"mensagem": "Último alerta", "dados": ultimo}

@app.post("/api/alertas/{alerta_id}/resolver", tags=["Emergencia"])
def marcar_alerta_resolvido(alerta_id: str):
    """Marca um alerta como resolvido"""
    try:
        logger.info(f"Tentando resolver alerta com ID: '{alerta_id}' (tipo: {type(alerta_id).__name__})")
        
        # Validar alerta_id
        if not alerta_id or alerta_id == 'undefined' or alerta_id == '':
            logger.warning(f"ID de alerta inválido recebido: '{alerta_id}'")
            return {"mensagem": f"ID de alerta inválido: '{alerta_id}'", "status": "ERROR"}
        
        if db_service:
            logger.info(f"Usando DynamoDB para resolver alerta {alerta_id}")
            sucesso = db_service.marcar_alerta_resolvido(alerta_id)
            if sucesso:
                logger.info(f"Alerta {alerta_id} marcado como resolvido com sucesso")
                return {"mensagem": "Alerta marcado como resolvido", "status": "OK"}
            else:
                logger.warning(f"Falha ao marcar alerta {alerta_id} como resolvido (não encontrado ou já resolvido)")
                # Verificar se o alerta existe
                todos_alertas = db_service.obter_todos_alertas(limite=100)
                ids_existentes = [a.get('id') for a in todos_alertas if a.get('id')]
                logger.info(f"IDs de alertas existentes: {ids_existentes[:5]}...")
                return {"mensagem": f"Alerta '{alerta_id}' não encontrado ou já resolvido", "status": "ERROR"}
        else:
            # Em modo memória, remover da lista (buscar por id ou id_alerta)
            global alertas_emergencia
            logger.info(f"Modo memória: buscando alerta {alerta_id} em {len(alertas_emergencia)} alertas")
            encontrado = False
            for a in alertas_emergencia:
                a_id = a.get('id') or a.get('id_alerta')
                logger.debug(f"Comparando: '{a_id}' com '{alerta_id}'")
                if a_id == alerta_id:
                    alertas_emergencia.remove(a)
                    encontrado = True
                    logger.info(f"Alerta {alerta_id} removido da lista (modo memória)")
                    break
            
            if encontrado:
                return {"mensagem": "Alerta removido", "status": "OK"}
            else:
                ids_na_memoria = [a.get('id') or a.get('id_alerta') for a in alertas_emergencia]
                logger.warning(f"Alerta {alerta_id} não encontrado na lista. IDs disponíveis: {ids_na_memoria}")
                return {"mensagem": f"Alerta '{alerta_id}' não encontrado na memória", "status": "ERROR"}
    except Exception as e:
        logger.error(f"Erro ao marcar alerta como resolvido: {e}", exc_info=True)
        return {"mensagem": f"Erro interno: {str(e)}", "status": "ERROR"}

@app.get("/api/alertas/contador", tags=["Emergencia"])
def obter_contador_alertas():
    """Retorna o número total de alertas de emergência"""
    if db_service:
        cont = db_service.contar_alertas()
        total = cont.get('total', 0)
        crit = cont.get('CRITICO', 0)
        alto = cont.get('ALTO', 0)
    else:
        total = len(alertas_emergencia)
        crit = len([a for a in alertas_emergencia if a['severidade'] == 'CRITICO'])
        alto = len([a for a in alertas_emergencia if a['severidade'] == 'ALTO'])
    logger.info(f"Total de alertas: {total} (Críticos: {crit}, Altos: {alto})")
    return {
        "total_alertas": total,
        "alertas_criticos": crit,
        "alertas_altos": alto,
        "alertas_medios": total - crit - alto,
        "mensagem": f"Total de {total} alertas de emergência"
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
    import random
    # Escolher aleatoriamente um dos 3 sensores disponíveis
    sensores_disponiveis = ["salaA-sensor01", "salaB-sensor02", "salaC-sensor03"]
    sensor_aleatorio = random.choice(sensores_disponiveis)
    
    # Simular diferentes tipos de emergência
    tipos_emergencia = [
        ("TEMPERATURA_CRITICA", f"Temperatura crítica detectada: 15.5°C - Fora da faixa segura!"),
        ("SENSOR_OFFLINE", f"Sensor {sensor_aleatorio} offline há mais de 5 minutos"),
        ("FALHA_ENERGIA", f"Falha de energia detectada no refrigerador - {sensor_aleatorio}"),
        ("PORTA_ABERTA", f"Porta do refrigerador aberta há mais de 2 minutos - {sensor_aleatorio}")
    ]
    
    tipo_alerta, mensagem = random.choice(tipos_emergencia)
    temperatura = random.uniform(10.0, 20.0) if tipo_alerta == "TEMPERATURA_CRITICA" else 0.0
    
    alerta = criar_alerta_emergencia(
        id_sensor=sensor_aleatorio,
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
