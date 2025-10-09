# Scripts de Produção (AWS)

Scripts para deploy e execução na AWS real.

## Pré-requisitos

```bash
# Configurar credenciais AWS
aws configure

# Verificar credenciais
aws sts get-caller-identity

# Instalar SAM CLI
pip install aws-sam-cli
```

## Scripts Disponíveis

### `deploy_production.sh`

Deploy completo na AWS.

**Uso:**
```bash
bash scripts/production/deploy_production.sh
```

**Variáveis configuráveis:**
```bash
export STACK_NAME="bp-ecg-production"
export INPUT_BUCKET="bp-ecg-input-prod"
export OUTPUT_BUCKET="bp-ecg-output-prod"
export AWS_REGION="us-east-1"
bash scripts/production/deploy_production.sh
```

**O que faz:**
- Verifica credenciais AWS
- Cria buckets S3 com segurança habilitada
- Build com SAM usando container
- Deploy de Lambda e State Machines (simples + paralela)

### `execute_parallel.sh`

Executa processamento em paralelo de todos os PDFs no bucket.

**Uso:**
```bash
# Com configuração padrão
bash scripts/production/execute_parallel.sh

# Com configuração customizada
INPUT_BUCKET="meu-bucket" \
OUTPUT_BUCKET="meu-output" \
BATCH_SIZE=20 \
MAX_BATCHES=100 \
AWS_REGION="us-east-1" \
bash scripts/production/execute_parallel.sh
```

**Parâmetros:**
- `INPUT_BUCKET`: Bucket de entrada (default: bp-ecg-input-prod)
- `OUTPUT_BUCKET`: Bucket de saída (default: bp-ecg-output-prod)
- `BATCH_SIZE`: PDFs por batch (default: 10)
- `MAX_BATCHES`: Máximo de batches (default: 50)
- `AWS_REGION`: Região AWS (default: us-east-1)

**O que faz:**
- Lista todos os PDFs no bucket de entrada
- Agrupa em batches
- Executa State Machine paralela (MaxConcurrency: 500)
- Aguarda conclusão e mostra resultados

## Exemplos

### Deploy inicial
```bash
bash scripts/production/deploy_production.sh
```

### Upload de PDFs
```bash
aws s3 cp ./meus_pdfs/ s3://bp-ecg-input-prod/ --recursive
```

### Processar em paralelo
```bash
bash scripts/production/execute_parallel.sh
```

### Verificar resultados
```bash
aws s3 ls s3://bp-ecg-output-prod/ --recursive
aws s3 sync s3://bp-ecg-output-prod/ ./resultados/
```

## Monitoramento

```bash
# Ver stack outputs
aws cloudformation describe-stacks --stack-name bp-ecg-production

# Lambda logs
aws logs tail /aws/lambda/bp-ecg-anonymizer --follow

# State Machine executions
aws stepfunctions list-executions \
  --state-machine-arn <ARN> \
  --max-results 10
```

## Custos Estimados

### 100.000 PDFs
- Lambda: ~$14
- Step Functions: ~$0.25
- S3: ~$2
- **Total: ~$16**

### 1.000.000 PDFs
- Lambda: ~$140
- Step Functions: ~$2.50
- S3: ~$20
- **Total: ~$162**

## Cleanup

```bash
# Deletar stack
sam delete --stack-name bp-ecg-production

# Deletar buckets
aws s3 rm s3://bp-ecg-input-prod --recursive
aws s3 rb s3://bp-ecg-input-prod

aws s3 rm s3://bp-ecg-output-prod --recursive
aws s3 rb s3://bp-ecg-output-prod
```
