# BP-ECG ETL - Guia de Deploy e Execução

Guia completo para desenvolvimento local (LocalStack) e deploy em produção (AWS).

---

## Índice

1. [Desenvolvimento Local (LocalStack)](#desenvolvimento-local-localstack)
2. [Produção (AWS)](#produção-aws)
3. [Processamento Paralelo](#processamento-paralelo)
4. [Troubleshooting](#troubleshooting)

---

# Desenvolvimento Local (LocalStack)

Para testes locais sem custos AWS.

## Pré-requisitos Locais

```bash
# 1. Instalar dependências de desenvolvimento
pip install -e ".[dev]"

# 2. Verificar instalações
docker --version
samlocal --version
awslocal --version
```

## Deploy Local

### Passo 1: Iniciar LocalStack

```bash
docker-compose up -d

# Verificar saúde
curl http://localhost:4566/_localstack/health
```

### Passo 2: Deploy com SAM

```bash
bash scripts/local/deploy_localstack.sh
```

**O que o script faz:**
- Verifica LocalStack
- Cria buckets S3 (bp-ecg-input, bp-ecg-output)
- Faz upload de PDFs de teste (`test_data_local/`)
- Build com SAM usando container
- Deploy de Lambda e State Machines

**Output esperado:**
```
[INFO] Deploying to LocalStack using SAM
[OK] LocalStack is running
[INFO] Creating S3 buckets
[OK] Uploaded 13 test PDFs
[INFO] Building SAM application
[INFO] Deploying to LocalStack
[SUCCESS] Deployment completed
```

## Execução Local

### Opção 1: Processamento Simples (1 PDF)

```bash
bash scripts/local/execute_statemachine.sh test_data_local/exemplo_13.pdf
```

**Saída:**
```
[INFO] Executing state machine for: exemplo_13.pdf
[INFO] Uploading file
[OK] Upload completed
[INFO] Starting execution
[SUCCESS] Execution completed
[OK] File saved: resultado_exemplo_13_anonimizado.pdf (245K)
```

### Opção 2: Ver Resultados

```bash
# Listar arquivos processados
awslocal s3 ls s3://bp-ecg-output/

# Baixar resultado
awslocal s3 cp s3://bp-ecg-output/exemplo_13_anonimizado.pdf ./
```

## Parar LocalStack

```bash
docker-compose down
```

---

# Produção (AWS)

Deploy na AWS real.

## Pré-requisitos Produção

```bash
# 1. Configurar credenciais AWS
aws configure
# Access Key ID: <sua-key>
# Secret Access Key: <seu-secret>
# Default region: us-east-1

# 2. Verificar credenciais
aws sts get-caller-identity

# 3. Instalar SAM CLI
pip install aws-sam-cli
sam --version
```

## Deploy Produção

### Passo 1: Configurar Variáveis (Opcional)

```bash
export STACK_NAME="bp-ecg-production"
export INPUT_BUCKET="bp-ecg-input-prod"
export OUTPUT_BUCKET="bp-ecg-output-prod"
export AWS_REGION="us-east-1"
```

### Passo 2: Deploy

```bash
bash scripts/production/deploy_production.sh
```

**O que o script faz:**
- Verifica credenciais AWS
- Cria buckets S3 com segurança habilitada
- Build com SAM usando container
- Deploy de:
  - Lambda (bp-ecg-anonymizer)
  - State Machine Simples (bp-ecg-processor)
  - State Machine Paralela (bp-ecg-parallel-processor)
  - IAM Roles e Policies

**Output esperado:**
```
[INFO] Deploying to AWS Production
Stack: bp-ecg-production
Region: us-east-1
[OK] AWS Account: 123456789012
[OK] Input bucket created
[OK] Output bucket created
[INFO] Building SAM application
[INFO] Deploying to AWS
[SUCCESS] Production deployment completed
```

### Passo 3: Verificar Deploy

```bash
# Ver stack outputs
aws cloudformation describe-stacks \
  --stack-name bp-ecg-production \
  --query 'Stacks[0].Outputs'

# Listar Lambda
aws lambda list-functions \
  --query 'Functions[?starts_with(FunctionName, `bp-ecg`)].FunctionName'

# Listar State Machines
aws stepfunctions list-state-machines \
  --query 'stateMachines[?starts_with(name, `bp-ecg`)].name'
```

---

# Processamento Paralelo

Para processar grandes volumes de PDFs em produção.

## Como Funciona

1. Lista todos os PDFs no bucket de entrada
2. Agrupa em batches (padrão: 10 PDFs/batch)
3. Executa State Machine paralela
4. MaxConcurrency: 500 Lambdas simultâneas

## Execução

### Passo 1: Upload de PDFs

```bash
# Upload de diretório completo
aws s3 cp ./meus_pdfs/ s3://bp-ecg-input-prod/ --recursive

# Verificar upload
aws s3 ls s3://bp-ecg-input-prod/ --recursive | wc -l
```

### Passo 2: Executar Processamento

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

**Output esperado:**
```
[INFO] Parallel processing execution (PRODUCTION)
Region: us-east-1
Input Bucket: bp-ecg-input-prod
[OK] Found 1500 PDF(s)
[OK] Created 150 batch(es)
[INFO] Starting parallel execution
[SUCCESS] Parallel execution completed
Processed: 1500 PDFs in 150 batch(es)
Output: 1495 anonymized PDFs
```

### Passo 3: Monitorar

```bash
# Via console AWS
https://console.aws.amazon.com/states/

# Via CLI
aws stepfunctions describe-execution \
  --execution-arn <ARN-DA-EXECUÇÃO>
```

### Passo 4: Download Resultados

```bash
# Baixar todos os resultados
aws s3 sync s3://bp-ecg-output-prod/ ./resultados/

# Contar arquivos processados
aws s3 ls s3://bp-ecg-output-prod/ --recursive | wc -l
```

---

# Troubleshooting

## LocalStack

### LocalStack não inicia

```bash
# Verificar se Docker está rodando
docker ps

# Reiniciar LocalStack
docker-compose restart

# Ver logs
docker-compose logs localstack
```

### Erro: "Service 'X' is not enabled"

Adicione o serviço ao `docker-compose.yml`:
```yaml
SERVICES=s3,lambda,stepfunctions,iam,logs,cloudformation,events
```

### Lambda não processa

```bash
# Ver logs do container
docker-compose logs localstack | grep -i error

# Verificar Lambda existe
awslocal lambda list-functions

# Testar Lambda diretamente
awslocal lambda invoke \
  --function-name bp-ecg-anonymizer \
  --payload '{"Records":[{"s3":{"bucket":{"name":"bp-ecg-input"},"object":{"key":"test.pdf"}}}]}' \
  response.json
```

## Produção (AWS)

### Erro: Credenciais AWS

```bash
# Verificar credenciais
aws sts get-caller-identity

# Reconfigurar
aws configure
```

### Erro: Docker não encontrado

```bash
# Linux
sudo systemctl start docker

# macOS/Windows
# Inicie Docker Desktop
```

### Erro: SAM build falhou

```bash
# Sempre use container
sam build --use-container --template template.yaml

# Limpar cache e rebuildar
rm -rf .aws-sam/
sam build --use-container
```

### Erro: Bucket já existe

Buckets S3 são globalmente únicos. Use nome diferente:
```bash
export INPUT_BUCKET="bp-ecg-input-${RANDOM}"
export OUTPUT_BUCKET="bp-ecg-output-${RANDOM}"
bash deploy_production.sh
```

### Lambda Timeout

Aumente timeout no `template.yaml`:
```yaml
Timeout: 900  # 15 minutos
```

### Lambda Out of Memory

Aumente memória no `template.yaml`:
```yaml
MemorySize: 2048  # 2GB
```

## Processamento Paralelo

### State Machine não encontrada

```bash
# Listar state machines
aws stepfunctions list-state-machines --query 'stateMachines[*].name'

# Verificar nome correto
export STATE_MACHINE_NAME="bp-ecg-parallel-processor"
```

### Batches muito grandes

Reduzir tamanho:
```bash
BATCH_SIZE=5 bash scripts/production/execute_parallel.sh
```

### Timeout na execução

Aumentar timeout no script ou processar em partes menores:
```bash
MAX_BATCHES=20 bash scripts/production/execute_parallel.sh
```

---

# Comandos Úteis

## LocalStack

```bash
# Status completo
curl http://localhost:4566/_localstack/health | jq

# Listar recursos
awslocal s3 ls
awslocal lambda list-functions
awslocal stepfunctions list-state-machines

# Logs em tempo real
docker-compose logs -f localstack
```

## Produção

```bash
# Stack info
aws cloudformation describe-stacks --stack-name bp-ecg-production

# Lambda logs
aws logs tail /aws/lambda/bp-ecg-anonymizer --follow

# State Machine executions
aws stepfunctions list-executions \
  --state-machine-arn <ARN> \
  --max-results 10

# Custos estimados (CloudWatch)
aws ce get-cost-and-usage \
  --time-period Start=2025-01-01,End=2025-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost
```

---

# Custos Estimados (Produção)

## Por Volume

### 100.000 PDFs
- Lambda (1GB, 30s avg): ~$14
- Step Functions: ~$0.25
- S3 Storage + Transfer: ~$2
- **Total: ~$16**

### 1.000.000 PDFs
- Lambda: ~$140
- Step Functions: ~$2.50
- S3: ~$20
- **Total: ~$162**

### 10.000.000 PDFs
- Lambda: ~$1,400
- Step Functions: ~$25
- S3: ~$200
- **Total: ~$1,625**

## Otimizações de Custo

1. **Reduzir memória Lambda** (se possível):
   ```yaml
   MemorySize: 512  # Metade do custo
   ```

2. **Usar S3 Intelligent-Tiering** para outputs:
   ```bash
   aws s3api put-bucket-intelligent-tiering-configuration \
     --bucket bp-ecg-output-prod \
     --id auto-archive \
     --intelligent-tiering-configuration file://tiering.json
   ```

3. **Processar em horários off-peak** (menos concorrência)

---

# Cleanup

## LocalStack

```bash
# Parar e remover tudo
docker-compose down -v

# Remover imagens
docker rmi localstack/localstack:latest
```

## Produção

```bash
# Deletar stack (mantém buckets)
sam delete --stack-name bp-ecg-production

# Esvaziar e deletar buckets
aws s3 rm s3://bp-ecg-input-prod --recursive
aws s3 rb s3://bp-ecg-input-prod

aws s3 rm s3://bp-ecg-output-prod --recursive
aws s3 rb s3://bp-ecg-output-prod

# Verificar recursos órfãos
aws cloudformation list-stacks --query 'StackSummaries[?StackName==`bp-ecg-production`]'
```
