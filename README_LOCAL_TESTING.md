# 🧪 Testes Locais com LocalStack

Este guia explica como testar o pipeline BP-ECG ETL localmente usando LocalStack.

## 📋 Pré-requisitos

- Docker e Docker Compose instalados
- Python 3.12+
- AWS CLI instalado (para comandos opcionais)

## 🚀 Quick Start

### 1. Iniciar LocalStack

```bash
./scripts/start_localstack.sh
```

Este script irá:
- Iniciar o LocalStack com serviço S3
- Criar automaticamente os buckets `raw-pdfs` e `anon-pdfs`
- Verificar o status dos serviços

### 2. Testar o Pipeline

```bash
# Testar com um PDF de exemplo
python scripts/test_local.py test_data/exemplo1.pdf

# Listar buckets disponíveis
python scripts/test_local.py --list-buckets
```

### 3. Parar LocalStack

```bash
docker-compose down
```

## 📁 Estrutura

```
.
├── docker-compose.yml              # Configuração LocalStack
├── scripts/
│   ├── start_localstack.sh        # Inicia ambiente local
│   └── test_local.py              # Testa pipeline localmente
└── test_data/                     # PDFs de exemplo
```

## 🔧 Configuração

### Buckets S3

Por padrão, os seguintes buckets são criados:
- `raw-pdfs` - Bucket de entrada (PDFs originais)
- `anon-pdfs` - Bucket de saída (PDFs anonimizados)

### Endpoint LocalStack

O LocalStack está disponível em:
- URL: `http://localhost:4566`
- Região: `us-east-1`
- Credenciais: `test` / `test` (padrão)

## 📊 Comandos Úteis

### Listar arquivos nos buckets

```bash
# Bucket de entrada
aws --endpoint-url=http://localhost:4566 s3 ls s3://raw-pdfs/

# Bucket de saída
aws --endpoint-url=http://localhost:4566 s3 ls s3://anon-pdfs/
```

### Upload manual de PDF

```bash
aws --endpoint-url=http://localhost:4566 s3 cp \
  test_data/exemplo1.pdf s3://raw-pdfs/test/
```

### Download de PDF anonimizado

```bash
aws --endpoint-url=http://localhost:4566 s3 cp \
  s3://anon-pdfs/test/year=2025/month=01/day=07/anonymized_XXXX.pdf.gz \
  ./output.pdf.gz
```

### Ver logs do LocalStack

```bash
docker-compose logs -f localstack
```

## 🧪 Testes Automatizados

Para rodar os testes unitários:

```bash
# Apenas testes unitários (rápidos)
pytest tests/unit/ -v

# Todos os testes
pytest -v

# Com coverage
pytest --cov=bp_ecg_etl --cov-report=html
```

## 🐛 Troubleshooting

### LocalStack não inicia

```bash
# Verificar se porta 4566 está em uso
lsof -i :4566

# Limpar containers e volumes
docker-compose down -v
docker-compose up -d
```

### Buckets não são criados

```bash
# Recriar buckets manualmente
docker-compose up localstack-init
```

### Erro de conexão com S3

Certifique-se de que:
1. LocalStack está rodando: `docker-compose ps`
2. Health check passou: `curl http://localhost:4566/_localstack/health`
3. Endpoint está correto: `http://localhost:4566`

## 📝 Variáveis de Ambiente

Você pode customizar a configuração criando um arquivo `.env`:

```bash
# Buckets
INPUT_BUCKET=raw-pdfs
OUTPUT_BUCKET=anon-pdfs

# Região AWS
AWS_REGION=us-east-1

# Processamento
MAX_WORKERS=10
DPI_PAGE2_RENDER=150
```

## 🔄 Workflow de Teste

1. **Preparar ambiente**
   ```bash
   ./scripts/start_localstack.sh
   ```

2. **Testar com PDF**
   ```bash
   python scripts/test_local.py test_data/exemplo1.pdf
   ```

3. **Verificar output**
   ```bash
   ls -lh test_output/
   ```

4. **Limpar**
   ```bash
   docker-compose down
   rm -rf test_output/
   ```

## 🚀 Próximos Passos

Após validar localmente, você pode:

1. **Deploy para ECS**: `./scripts/deploy_ecs.sh`
2. **Rodar testes de integração**: `pytest tests/integration/ -v`
3. **Build Docker**: `docker build -t bp-ecg-etl:latest .`
