# Deploy na AWS

Tutorial simplificado para deploy do BP-ECG ETL na AWS.

## Pré-requisitos

1. **AWS CLI configurado**
```bash
aws configure
# Insira: Access Key, Secret Key, região (us-east-1)
```

2. **Docker instalado e rodando**
```bash
docker --version
```

3. **AWS SAM CLI**
```bash
# Já está no pyproject.toml
uv sync --extra dev
sam --version
```

## Passo 1: Configurar Buckets

Edite `template.yaml` (linhas 17-18):

```yaml
INPUT_BUCKET: "seu-bucket-entrada"
OUTPUT_BUCKET: "seu-bucket-saida"
```

Crie os buckets:
```bash
aws s3 mb s3://seu-bucket-entrada
aws s3 mb s3://seu-bucket-saida
```

## Passo 2: Build (com Docker)

```bash
sam build --use-container
```

**O que acontece:**
- SAM baixa imagem Docker oficial com Python 3.12
- Instala dependências do `requirements.txt`
- Cria ZIP otimizado em `.aws-sam/build/`
- Tempo: ~2-5 minutos

**Output esperado:**
```
Build Succeeded

Built Artifacts  : .aws-sam/build
Built Template   : .aws-sam/build/template.yaml
```

## Passo 3: Deploy (primeira vez)

```bash
sam deploy --guided
```

**Responda:**
```
Stack Name: bp-ecg-etl-stack
AWS Region: us-east-1
Confirm changes before deploy [Y/n]: n
Allow SAM CLI IAM role creation [Y/n]: Y
Disable rollback [y/N]: N
BpEcgProcessorFunction has no authentication [y/N]: y
Save arguments to config file [Y/n]: Y
SAM configuration file [samconfig.toml]: (Enter)
SAM configuration environment [default]: (Enter)
```

**O que acontece:**
- SAM cria bucket S3 gerenciado
- Faz upload do ZIP (~150MB)
- Cria CloudFormation stack
- Deploy Lambda (10GB RAM)
- Cria Step Functions State Machine
- Configura IAM roles
- Tempo: ~5-10 minutos

**Output esperado:**
```
Successfully created/updated stack - bp-ecg-etl-stack in us-east-1

Outputs:
ProcessorFunctionArn: arn:aws:lambda:us-east-1:123456789:function:bp-ecg-etl-stack-BpEcgProcessorFunction-ABC123
StateMachineArn: arn:aws:states:us-east-1:123456789:stateMachine:BpEcgStateMachine-DEF456
```

## Passo 4: Deploys Seguintes

Após primeira vez, basta:

```bash
sam build --use-container
sam deploy
```

Sem `--guided` - usa configuração salva.

## Passo 5: Upload PDFs

```bash
aws s3 cp pasta_pdfs/ s3://seu-bucket-entrada/ --recursive
```

## Passo 6: Executar Processamento

**Opção 1: Manual (recomendado)** - especificando ARN:

```bash
# Pegar ARN da State Machine do output do deploy
python scripts/prepare_and_deploy.py \
  --bucket seu-bucket-entrada \
  --state-machine-arn arn:aws:states:us-east-1:123456789:stateMachine:BpEcgStateMachine-DEF456
```

**Opção 2: Automático** - busca do CloudFormation:

```bash
python scripts/prepare_and_deploy.py --bucket seu-bucket-entrada
```

**Output esperado:**
```
[1/4] Verificando State Machine...
  ✓ State Machine encontrada

[2/4] Listando PDFs em s3://seu-bucket-entrada/...
Encontrados 1,500,000 PDFs

[3/4] Criados 7,500 lotes de até 200 arquivos

[4/4] Iniciando Step Function...
  State Machine: arn:aws:states:...
  Total de lotes: 7,500
  Total de arquivos: 1,500,000

======================================================================
PROCESSAMENTO INICIADO COM SUCESSO
======================================================================
Execution ARN: arn:aws:states:us-east-1:...

Monitore em: https://console.aws.amazon.com/states/
======================================================================
```

## Passo 7: Monitorar

Abra console AWS Step Functions:
```
https://console.aws.amazon.com/states/
```

Ou via CLI:
```bash
aws stepfunctions describe-execution \
  --execution-arn <ARN-DA-EXECUÇÃO>
```

## Passo 8: Ver Resultados

```bash
aws s3 ls s3://seu-bucket-saida/ --recursive
```

## Troubleshooting

### Erro: Docker não encontrado
```bash
# Instalar Docker Desktop ou
sudo systemctl start docker
```

### Erro: Python 3.12 não encontrado (sem --use-container)
```bash
# Solução: sempre use --use-container
sam build --use-container
```

### Erro: Permissões AWS
```bash
aws sts get-caller-identity  # Verifica credenciais
```

### Atualizar código
```bash
# Modificou código Python?
sam build --use-container
sam deploy
```

## Comandos Resumidos

```bash
# Build + Deploy
sam build --use-container && sam deploy

# Executar
python scripts/prepare_and_deploy.py --bucket seu-bucket-entrada

# Logs
sam logs -n BpEcgProcessorFunction --tail
```

## Custos Estimados

### 100.000 PDFs:
- Lambda: ~$14
- Step Functions: ~$0.25
- S3: ~$2
- **Total: ~$16**

### 1.5M PDFs:
- Lambda: ~$180
- Step Functions: ~$3.75
- S3: ~$30
- **Total: ~$210**

## Deletar Stack

Para remover tudo:

```bash
sam delete

# Deletar buckets (cuidado!)
aws s3 rb s3://seu-bucket-entrada --force
aws s3 rb s3://seu-bucket-saida --force
```
