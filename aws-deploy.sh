#!/bin/bash

# Script para deploy do ImmunoTrack na AWS

echo "Iniciando deploy do ImmunoTrack na AWS..."

# Configurações
AWS_REGION="us-east-1"
ECR_REPOSITORY="immunotrack"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Configurações:${NC}"
echo "  - Região AWS: $AWS_REGION"
echo "  - Account ID: $AWS_ACCOUNT_ID"
echo "  - ECR Repository: $ECR_REPOSITORY"
echo ""

# 1. Criar repositório ECR se não existir
echo -e "${YELLOW}1. Configurando ECR...${NC}"
aws ecr describe-repositories --repository-names $ECR_REPOSITORY --region $AWS_REGION > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "  Criando repositório ECR..."
    aws ecr create-repository --repository-name $ECR_REPOSITORY --region $AWS_REGION
else
    echo "  Repositório ECR já existe"
fi

# 2. Fazer login no ECR
echo -e "${YELLOW}2. Fazendo login no ECR...${NC}"
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# 3. Build e push das imagens
echo -e "${YELLOW}3. Buildando e enviando imagens...${NC}"

# Collector Service
echo "  Buildando collector-service..."
docker build -t $ECR_REPOSITORY-collector ./collector-service
docker tag $ECR_REPOSITORY-collector:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY-collector:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY-collector:latest

# Sensor Service
echo "  Buildando sensor-service..."
docker build -t $ECR_REPOSITORY-sensor ./sensor-service
docker tag $ECR_REPOSITORY-sensor:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY-sensor:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY-sensor:latest

echo -e "${GREEN}Deploy concluído!${NC}"
echo ""
echo -e "${YELLOW}Próximos passos:${NC}"
echo "  1. Criar cluster ECS ou EKS"
echo "  2. Configurar Load Balancer"
echo "  3. Configurar Auto Scaling"
echo "  4. Configurar CloudWatch para monitoramento"
echo ""
echo -e "${YELLOW}URLs das imagens:${NC}"
echo "  Collector: $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY-collector:latest"
echo "  Sensor: $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY-sensor:latest"