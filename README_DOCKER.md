# 🐳 Guia de Execução Local com Docker

## 📋 Pré-requisitos

- Docker e Docker Compose instalados
- AWS CLI instalado (opcional, para testes com AWS real)

---

## 🚀 Método 1: Docker Compose + LocalStack (Recomendado)

### **1. Configure as variáveis de ambiente**

```bash
# Copie o arquivo de exemplo
cp .env.local .env

# Edite se necessário
nano .env
```

### **2. Prepare os dados de teste**

```bash
# Crie diretório para PDFs de entrada
mkdir -p test_data_local

# Copie seus PDFs de teste
cp /caminho/para/seus/pdfs/*.pdf test_data_local/
```

### **3. Inicie LocalStack e a aplicação**

```bash
# Inicia LocalStack (S3 local) e a aplicação
docker-compose -f docker-compose.local.yml up -d

# Veja os logs
docker-compose -f docker-compose.local.yml logs -f bp-ecg-etl
```

### **4. Crie os buckets no LocalStack**

```bash
# Entre no container LocalStack
docker-compose -f docker-compose.local.yml exec localstack bash

# Crie os buckets
aws --endpoint-url=http://localhost:4566 s3 mb s3://raw-pdfs
aws --endpoint-url=http://localhost:4566 s3 mb s3://anon-pdfs

# Upload de PDFs de teste
aws --endpoint-url=http://localhost:4566 s3 cp /tmp/test_data/ s3://raw-pdfs/ --recursive
```

### **5. Execute o processamento**

```bash
# Reinicie a aplicação para processar
docker-compose -f docker-compose.local.yml restart bp-ecg-etl

# Acompanhe o processamento
docker-compose -f docker-compose.local.yml logs -f bp-ecg-etl
```

### **6. Verifique os resultados**

```bash
# Liste os PDFs processados
aws --endpoint-url=http://localhost:4566 s3 ls s3://anon-pdfs/ --recursive

# Baixe os resultados
aws --endpoint-url=http://localhost:4566 s3 cp s3://anon-pdfs/ ./test_output/ --recursive
```

### **7. Pare os containers**

```bash
docker-compose -f docker-compose.local.yml down
```

---

## 🔧 Método 2: Docker Run (sem Docker Compose)

### **1. Build da imagem**

```bash
docker build -t bp-ecg-etl:local .
```

### **2. Execute com variáveis de ambiente**

```bash
docker run --rm \
  -e INPUT_BUCKET=raw-pdfs \
  -e OUTPUT_BUCKET=anon-pdfs \
  -e AWS_REGION=us-east-1 \
  -e AWS_ACCESS_KEY_ID=sua_key \
  -e AWS_SECRET_ACCESS_KEY=sua_secret \
  -e MAX_WORKERS=10 \
  -e QUEUE_SIZE=50 \
  bp-ecg-etl:local
```

### **3. Ou use arquivo .env**

```bash
docker run --rm \
  --env-file .env \
  bp-ecg-etl:local
```

---

## 📊 Método 3: AWS Real (Produção)

### **1. Configure credenciais AWS**

```bash
# Edite .env e configure:
# - AWS_ACCESS_KEY_ID
# - AWS_SECRET_ACCESS_KEY
# - INPUT_BUCKET (bucket real)
# - OUTPUT_BUCKET (bucket real)
# - Remova AWS_ENDPOINT_URL
```

### **2. Execute**

```bash
docker run --rm \
  --env-file .env \
  bp-ecg-etl:local
```

---

## 🎛️ Variáveis de Ambiente Importantes

| Variável | Valor Padrão | Descrição |
|----------|--------------|-----------|
| `INPUT_BUCKET` | `raw-pdfs` | Bucket de entrada |
| `OUTPUT_BUCKET` | `anon-pdfs` | Bucket de saída |
| `AWS_REGION` | `us-east-1` | Região AWS |
| `MAX_WORKERS` | `100` | Número de workers |
| `QUEUE_SIZE` | `400` | Tamanho da fila |
| `AWS_ENDPOINT_URL` | - | URL para LocalStack |

### **Valores recomendados para ambiente:**

**Testes locais (poucos PDFs):**
```bash
MAX_WORKERS=10
QUEUE_SIZE=50
```

**Produção (8 vCPUs + 16GB):**
```bash
MAX_WORKERS=100
QUEUE_SIZE=400
```

**Produção (4 vCPUs + 8GB):**
```bash
MAX_WORKERS=50
QUEUE_SIZE=200
```

---

## 🐛 Troubleshooting

### **Erro: "Cannot connect to S3"**
```bash
# Verifique se LocalStack está rodando
docker-compose -f docker-compose.local.yml ps

# Verifique logs do LocalStack
docker-compose -f docker-compose.local.yml logs localstack
```

### **Erro: "Access Denied"**
```bash
# Para LocalStack, use credenciais dummy:
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test

# Para AWS real, verifique suas credenciais
aws sts get-caller-identity
```

### **Imagem muito grande**
```bash
# Use a versão Alpine otimizada (já configurada no Dockerfile)
# Tamanho esperado: ~100 MB
docker images | grep bp-ecg-etl
```

### **Memória insuficiente**
```bash
# Reduza MAX_WORKERS
MAX_WORKERS=10
QUEUE_SIZE=50
```

---

## 📦 Scripts Úteis

### **Script de setup completo:**

```bash
#!/bin/bash
# setup_local.sh

# Cria estrutura de diretórios
mkdir -p test_data_local test_output

# Copia .env
cp .env.local .env

# Build da imagem
docker build -t bp-ecg-etl:local .

# Inicia LocalStack
docker-compose -f docker-compose.local.yml up -d localstack

# Aguarda LocalStack ficar pronto
sleep 5

# Cria buckets
aws --endpoint-url=http://localhost:4566 s3 mb s3://raw-pdfs
aws --endpoint-url=http://localhost:4566 s3 mb s3://anon-pdfs

echo "✅ Setup completo! Agora:"
echo "1. Coloque PDFs em test_data_local/"
echo "2. Execute: docker-compose -f docker-compose.local.yml up bp-ecg-etl"
```

### **Script de limpeza:**

```bash
#!/bin/bash
# cleanup.sh

docker-compose -f docker-compose.local.yml down -v
rm -rf test_output/*
docker system prune -f
```

---

## 🎉 Exemplo Completo

```bash
# 1. Setup inicial
cp .env.local .env
mkdir -p test_data_local

# 2. Adicione PDFs de teste
cp exemplo*.pdf test_data_local/

# 3. Inicie tudo
docker-compose -f docker-compose.local.yml up -d

# 4. Crie buckets
aws --endpoint-url=http://localhost:4566 s3 mb s3://raw-pdfs
aws --endpoint-url=http://localhost:4566 s3 mb s3://anon-pdfs

# 5. Upload de PDFs
aws --endpoint-url=http://localhost:4566 s3 sync test_data_local/ s3://raw-pdfs/

# 6. Execute processamento
docker-compose -f docker-compose.local.yml restart bp-ecg-etl

# 7. Veja logs
docker-compose -f docker-compose.local.yml logs -f bp-ecg-etl

# 8. Baixe resultados
mkdir -p test_output
aws --endpoint-url=http://localhost:4566 s3 sync s3://anon-pdfs/ test_output/

# 9. Limpe
docker-compose -f docker-compose.local.yml down
```
