# Usar imagem Python oficial
FROM python:3.9-slim

# Instalar curl e libcap2-bin para setcap (permitir porta 80 sem root)
RUN apt-get update && apt-get install -y curl libcap2-bin && rm -rf /var/lib/apt/lists/*

# Criar usuário não-root
RUN useradd --create-home --shell /bin/bash app

# Definir diretório de trabalho
WORKDIR /app

# Copiar arquivo de dependências
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY app.py .
COPY notificacoes_aws.py .
COPY dynamodb_basic.py .
COPY service_discovery.py .
COPY sqs_client.py .
COPY mqtt_subscriber.py .

# Dar permissão para usar porta 80 sem ser root (setcap CAP_NET_BIND_SERVICE)
RUN setcap 'cap_net_bind_service=+ep' /usr/local/bin/python3.9 || true

# Mudar para usuário não-root
USER app

# Expor porta
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:80/saude || exit 1

# Comando para executar a aplicação
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]
