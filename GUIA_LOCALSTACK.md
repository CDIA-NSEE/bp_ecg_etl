# 🧪 Guia LocalStack - BP-ECG ETL

Teste completo com S3 + Lambda + Step Functions.

## 📋 Pré-requisitos

```bash
# Docker rodando
docker --version

# AWS CLI configurado
aws --version

# Python 3.11+
python3 --version
```

## 🚀 Passo 1: Iniciar LocalStack

```bash
# Subir LocalStack (S3 + Lambda + Step Functions)
docker-compose up -d

# Verificar
docker-compose ps
```

## 🔧 Passo 2: Setup Completo

Execute o script de setup que cria **tudo automaticamente**:

```bash
# Dar permissão
chmod +x setup_localstack.sh

# Executar
bash setup_localstack.sh
```

### O que o script faz:

1. ✅ Cria buckets S3 (`bp-ecg-input`, `bp-ecg-output`)
2. ✅ Cria pacote Lambda (`lambda_package.zip`)
3. ✅ Cria IAM Roles
4. ✅ Faz deploy da Lambda (`bp-ecg-anonymizer`)
5. ✅ Cria State Machine (`bp-ecg-processor`)

**Output esperado:**
```
============================================================
✅ SETUP CONCLUÍDO
============================================================

📋 Recursos criados:
  • Buckets S3: bp-ecg-input, bp-ecg-output
  • Lambda: bp-ecg-anonymizer
  • State Machine: bp-ecg-processor
```

## 🧪 Passo 3: Testar com PDF

```bash
# Dar permissão
chmod +x execute_statemachine.sh

# Executar com seu PDF
bash execute_statemachine.sh ".test_data/exemplo 1.PDF"
```

### O que acontece:

1. 📤 **Upload** do PDF para S3 input
2. ⚡ **Inicia** Step Functions
3. 🔄 **Processa** via Lambda (anonimização)
4. 💾 **Salva** resultado no S3 output
5. 📥 **Baixa** resultado automaticamente

**Output esperado:**
```
🚀 Executando State Machine para: exemplo 1.PDF

📤 Fazendo upload...
✓ Upload concluído: s3://bp-ecg-input/exemplo 1.PDF

⚡ Executando State Machine...
✓ Execução iniciada

⏳ Aguardando conclusão...
✅ Execução concluída com sucesso!

📥 Baixando resultado...
✓ Arquivo salvo: resultado_exemplo 1_anonimizado.pdf (2.5M)

✅ Processo concluído!
```

## 📊 Verificações Manuais

### Ver buckets:
```bash
aws --endpoint-url=http://localhost:4566 s3 ls
```

### Ver arquivos no bucket:
```bash
aws --endpoint-url=http://localhost:4566 s3 ls s3://bp-ecg-output/
```

### Ver State Machines:
```bash
aws --endpoint-url=http://localhost:4566 stepfunctions list-state-machines
```

### Ver execuções:
```bash
aws --endpoint-url=http://localhost:4566 stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:000000000000:stateMachine:bp-ecg-processor
```

### Ver logs (terminal separado):
```bash
docker-compose logs -f
```

## 🔁 Processar vários PDFs

```bash
# Processar múltiplos arquivos
for pdf in .test_data/*.PDF; do
    bash execute_statemachine.sh "$pdf"
done
```

## 🧹 Limpeza

### Limpar buckets:
```bash
aws --endpoint-url=http://localhost:4566 s3 rm s3://bp-ecg-input/ --recursive
aws --endpoint-url=http://localhost:4566 s3 rm s3://bp-ecg-output/ --recursive
```

### Reiniciar LocalStack:
```bash
docker-compose restart
```

### Parar e limpar tudo:
```bash
docker-compose down -v
```

## ❌ Troubleshooting

### LocalStack não conecta:
```bash
# Verificar se está rodando
docker-compose ps

# Ver logs
docker-compose logs

# Reiniciar
docker-compose restart
```

### Lambda falha:
```bash
# Ver logs detalhados
docker-compose logs -f localstack | grep lambda

# Recriar pacote
bash scripts/build_zip.sh
bash setup_localstack.sh
```

### State Machine não encontrada:
```bash
# Listar todas
aws --endpoint-url=http://localhost:4566 stepfunctions list-state-machines

# Recriar
bash setup_localstack.sh
```

### Execução falha:
```bash
# Ver detalhes da última execução
aws --endpoint-url=http://localhost:4566 stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:000000000000:stateMachine:bp-ecg-processor \
  --max-results 1

# Ver logs completos
docker-compose logs -f
```

## 📝 Arquivos Criados

- `docker-compose.yml` - Configuração LocalStack
- `setup_localstack.sh` - Setup automatizado
- `execute_statemachine.sh` - Execução de testes
- `statemachine/simple_processor.asl.json` - Definição State Machine

## 🎯 Fluxo Completo

```
PDF original
    ↓ (upload S3)
Step Functions
    ↓ (invoca)
Lambda Function
    ↓ (processa)
  • Página 1: Anonimização vetorial
  • Página 2: Rasterização 450 DPI + tarjas
    ↓ (salva S3)
PDF anonimizado
```

## ⚙️ Configurações

### Ajustar DPI:
Edite `bp_ecg_etl/config.py`:
```python
DPI_PAGE2_RENDER = 450  # 300, 450, 600
```

Depois re-execute setup:
```bash
bash setup_localstack.sh
```

### Ajustar coordenadas de redação:
Edite `bp_ecg_etl/config.py`:
```python
PAGE2_REDACT_COORDS = [
    (0.02, 0.10, 0.12, 0.17),  # Ajustar aqui
]
```

## 🚀 Próximos Passos

Após validar LocalStack:
1. ✅ Teste com múltiplos PDFs
2. ✅ Ajuste coordenadas de anonimização
3. ✅ Deploy em AWS real usando SAM/CDK
