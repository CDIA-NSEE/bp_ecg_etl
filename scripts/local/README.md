# Scripts de Desenvolvimento Local (LocalStack)

Scripts para testes e desenvolvimento local usando LocalStack.

## Pré-requisitos

```bash
# Instalar dependências
pip install -e ".[dev]"

# Iniciar LocalStack
docker-compose up -d
```

## Scripts Disponíveis

### `deploy_localstack.sh`

Deploy completo no LocalStack.

**Uso:**
```bash
bash scripts/local/deploy_localstack.sh
```

**O que faz:**
- Verifica se LocalStack está rodando
- Cria buckets S3 (bp-ecg-input, bp-ecg-output)
- Faz upload de PDFs de teste de `test_data_local/`
- Build com SAM usando container
- Deploy de Lambda e State Machines

### `execute_statemachine.sh`

Executa processamento de um único PDF.

**Uso:**
```bash
bash scripts/local/execute_statemachine.sh test_data_local/exemplo.pdf
```

**O que faz:**
- Upload do PDF para S3
- Executa State Machine simples
- Aguarda conclusão
- Baixa resultado automaticamente

## Exemplos

```bash
# Deploy inicial
bash scripts/local/deploy_localstack.sh

# Processar PDF
bash scripts/local/execute_statemachine.sh test_data_local/exemplo_13.pdf

# Ver resultados
awslocal s3 ls s3://bp-ecg-output/
```

## Troubleshooting

### LocalStack não inicia
```bash
docker ps
docker-compose restart
docker-compose logs localstack
```

### Lambda não processa
```bash
docker-compose logs localstack | grep -i error
awslocal lambda list-functions
```
