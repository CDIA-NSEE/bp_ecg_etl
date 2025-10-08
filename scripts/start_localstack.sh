#!/bin/bash
# Script para iniciar LocalStack e preparar ambiente de testes

set -e

echo "🚀 Iniciando LocalStack..."
docker-compose up -d localstack

echo "⏳ Aguardando LocalStack estar pronto..."
sleep 10

echo "🪣 Criando buckets S3..."
docker-compose up localstack-init

echo "✅ LocalStack iniciado com sucesso!"
echo ""
echo "📊 Status dos serviços:"
docker-compose ps

echo ""
echo "🔍 Buckets disponíveis:"
aws --endpoint-url=http://localhost:4566 s3 ls

echo ""
echo "💡 Para testar o pipeline:"
echo "   python scripts/test_local.py test_data/exemplo1.pdf"
echo ""
echo "💡 Para parar o LocalStack:"
echo "   docker-compose down"
