#!/bin/bash
# Script simples para deploy da função Lambda para LocalStack

set -e

echo "🚀 BP-ECG ETL - Deploy Simples para LocalStack"
echo "=============================================="

# Configurações
FUNCTION_NAME="bp-ecg-etl-anonymizer"
HANDLER="bp_ecg_etl.main.lambda_handler"
RUNTIME="python3.12"
LOCALSTACK_ENDPOINT="http://localhost:4566"

# Configurar AWS CLI para LocalStack
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

echo "📦 Criando pacote ZIP..."

# Criar diretório temporário
TEMP_DIR=$(mktemp -d)
ZIP_FILE="$TEMP_DIR/lambda-function.zip"

# Copiar código fonte
cp -r bp_ecg_etl "$TEMP_DIR/"

# Instalar dependências com uv (mais rápido) - versão otimizada para Lambda
echo "📚 Instalando dependências essenciais..."
uv pip install -r requirements-lambda.txt --target "$TEMP_DIR/" --quiet

# Criar ZIP
cd "$TEMP_DIR"
zip -r lambda-function.zip . -q
cd - > /dev/null

echo "✅ Pacote criado: $ZIP_FILE"

echo "🪣 Criando buckets S3..."
aws s3 mb s3://raw-pdfs --endpoint-url $LOCALSTACK_ENDPOINT 2>/dev/null || echo "   Bucket raw-pdfs já existe"
aws s3 mb s3://anon-pdfs --endpoint-url $LOCALSTACK_ENDPOINT 2>/dev/null || echo "   Bucket anon-pdfs já existe"

echo "🚀 Fazendo deploy da função Lambda..."

# Criar arquivo de configuração de ambiente
ENV_FILE="$TEMP_DIR/env.json"
cat > "$ENV_FILE" << 'EOF'
{
  "Variables": {
    "INPUT_BUCKET": "raw-pdfs",
    "OUTPUT_BUCKET": "anon-pdfs",
    "AWS_REGION": "us-east-1",
    "DPI_PAGE2_RENDER": "150",
    "LINE_TOLERANCE": "5",
    "PREVLINE_TOLERANCE": "20",
    "PADDING": "2"
  }
}
EOF

# Tentar atualizar função existente primeiro
if aws lambda get-function --function-name $FUNCTION_NAME --endpoint-url $LOCALSTACK_ENDPOINT >/dev/null 2>&1; then
    echo "♻️  Atualizando função existente..."
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://$ZIP_FILE \
        --endpoint-url $LOCALSTACK_ENDPOINT >/dev/null
    
    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --environment file://$ENV_FILE \
        --endpoint-url $LOCALSTACK_ENDPOINT >/dev/null
else
    echo "🆕 Criando nova função..."
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime $RUNTIME \
        --role arn:aws:iam::000000000000:role/lambda-role \
        --handler $HANDLER \
        --zip-file fileb://$ZIP_FILE \
        --timeout 900 \
        --memory-size 3008 \
        --environment file://$ENV_FILE \
        --endpoint-url $LOCALSTACK_ENDPOINT >/dev/null
fi

echo "✅ Deploy realizado com sucesso!"

# Configurar logs do CloudWatch (se disponível)
echo "📋 Configurando logs..."
aws logs create-log-group --log-group-name "/aws/lambda/$FUNCTION_NAME" --endpoint-url $LOCALSTACK_ENDPOINT 2>/dev/null || echo "   Log group já existe ou serviço não disponível"

# Configurar trigger automático S3 → Lambda
echo "🔗 Configurando trigger S3 → Lambda..."

# Dar permissão para S3 invocar a Lambda
aws lambda add-permission \
    --function-name $FUNCTION_NAME \
    --statement-id s3-trigger \
    --action lambda:InvokeFunction \
    --principal s3.amazonaws.com \
    --source-arn "arn:aws:s3:::raw-pdfs" \
    --endpoint-url $LOCALSTACK_ENDPOINT 2>/dev/null || echo "   Permissão já existe"

# Criar configuração de notificação S3
cat > /tmp/s3-notification.json << EOF
{
  "LambdaFunctionConfigurations": [
    {
      "Id": "bp-ecg-etl-trigger",
      "LambdaFunctionArn": "arn:aws:lambda:us-east-1:000000000000:function:$FUNCTION_NAME",
      "Events": ["s3:ObjectCreated:*"],

    }
  ]
}
EOF

# Aplicar configuração de notificação
aws s3api put-bucket-notification-configuration \
    --bucket raw-pdfs \
    --notification-configuration file:///tmp/s3-notification.json \
    --endpoint-url $LOCALSTACK_ENDPOINT && echo "✅ Trigger S3 configurado!" || echo "⚠️  Erro ao configurar trigger"

# Limpar arquivo temporário
rm -f /tmp/s3-notification.json

# Limpar arquivos temporários
rm -rf "$TEMP_DIR"

echo ""
echo "📋 Informações da função:"
echo "   Nome: $FUNCTION_NAME"
echo "   Handler: $HANDLER"
echo "   Runtime: $RUNTIME"
echo "   Timeout: 900s (15 minutos)"
echo "   Memory: 3008MB (~3GB)"
echo "   Endpoint: $LOCALSTACK_ENDPOINT"
echo ""
echo "🧪 Para testar (TRIGGER AUTOMÁTICO):"
echo "   # Configurar credenciais"
echo "   export AWS_ACCESS_KEY_ID=test"
echo "   export AWS_SECRET_ACCESS_KEY=test"
echo "   export AWS_DEFAULT_REGION=us-east-1"
echo ""
echo "   # 1. Fazer upload de PDF (dispara Lambda automaticamente!)"
echo "   aws s3 cp exemplo.pdf s3://raw-pdfs/ --endpoint-url $LOCALSTACK_ENDPOINT"
echo ""
echo "   # 2. Aguardar alguns segundos para processamento..."
echo "   sleep 5"
echo ""
echo "   # 3. Verificar PDF anonimizado (deve aparecer automaticamente!)"
echo "   aws s3 ls s3://anon-pdfs/ --endpoint-url $LOCALSTACK_ENDPOINT"
echo ""
echo "   # 4. Ver logs do processamento automático"
echo "   aws logs tail /aws/lambda/$FUNCTION_NAME --endpoint-url $LOCALSTACK_ENDPOINT"
echo ""
echo "   🎆 A Lambda é disparada AUTOMATICAMENTE quando você envia um PDF!"
echo ""
echo "🎉 Deploy completo!"
