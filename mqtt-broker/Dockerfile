FROM eclipse-mosquitto:2.0

# Copiar configuração customizada
COPY mosquitto.conf /mosquitto/config/mosquitto.conf

# Criar diretórios necessários
RUN mkdir -p /mosquitto/data /mosquitto/log

# Expor portas
EXPOSE 1883 9001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD mosquitto_sub -h localhost -t '$SYS/#' -C 1 || exit 1

