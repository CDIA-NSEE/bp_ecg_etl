# Fluxo de Processamento Simplificado

## Arquitetura

```
Script Local → Step Functions → 500 Lambdas → S3 Output
```

## Componentes

### 1. Script de Execução (`execute_parallel.sh`)
- Lista PDFs do S3 de entrada
- Divide em lotes (default: 10 PDFs/batch)
- Cria payload JSON com todos os lotes
- Inicia Step Function paralela

### 2. Step Functions
- **Simples** (`bp-ecg-processor`): Processa 1 PDF por vez (LocalStack)
- **Paralela** (`bp-ecg-parallel-processor`): MaxConcurrency 500 (Produção)
- Recebe array com todos os lotes
- Invoca Lambda para cada lote
- Garante máximo de 500 execuções simultâneas

### 3. Lambda Processor (`s3_handler.py`)
- Recebe evento S3 (1 ou mais PDFs)
- Processa com 15 workers assíncronos
- Para cada PDF:
  - Download do S3
  - Anonimiza página 1
  - Extrai página 2 como PNG
  - Mescla e comprime (ZIP)
  - Upload para S3 de saída (.pdf.zip)

## Fluxo Passo a Passo

### Execução do Script

```bash
# Produção (AWS)
bash scripts/production/execute_parallel.sh

# LocalStack (testes)
bash scripts/local/execute_statemachine.sh test_data_local/exemplo.pdf
```

**O que acontece:**

1. Script conecta no S3
2. Lista todos os arquivos `.pdf` no bucket
3. Divide em grupos de 200: `[lote1, lote2, ..., loteN]`
4. Cria payload:
```json
{
  "batches": [
    {"keys": ["file1.pdf", ..., "file200.pdf"]},
    {"keys": ["file201.pdf", ..., "file400.pdf"]},
    ...
  ]
}
```
5. Chama API Step Functions: `StartExecution`
6. Retorna ARN da execução

**Tempo:** ~1-2 minutos para 1.5M arquivos

### Step Functions Executa

**State Machine:**
```json
{
  "Type": "Map",
  "ItemsPath": "$.batches",
  "MaxConcurrency": 500,
  "Iterator": {
    "Type": "Task",
    "Resource": "Lambda"
  }
}
```

**O que acontece:**

1. Recebe 1500 lotes (exemplo com 1.5M arquivos)
2. Para cada lote, cria task de invocação Lambda
3. **Limita a 500 simultâneas** (MaxConcurrency)
4. Invoca primeiro grupo de 500 Lambdas
5. Assim que 1 termina, invoca próxima (501, 502, etc.)
6. Continua até processar todos os 1500 lotes
7. Retry automático em caso de erro (3x)

**Tempo:** ~7-8 horas para 1.5M arquivos

### Lambda Processa

**Event recebido:**
```json
{
  "keys": ["file1.pdf", "file2.pdf", ..., "file200.pdf"]
}
```

**O que acontece:**

1. Cria fila com 200 arquivos
2. Inicia 15 workers assíncronos
3. Cada worker:
   - Pega arquivo da fila
   - Baixa do S3 (~0.5s)
   - Processa (anonimiza + PNG + merge) (~2-3s)
   - Upload resultado (~0.5s)
   - Repete até fila vazia ou timeout (14.5 min)
4. Retorna sumário

**Tempo por PDF:** ~3-4 segundos
**Throughput:** ~200 arquivos por Lambda (100% do lote)

## Pipeline de Processamento PDF

Para cada PDF:

```
1. Download S3 (INPUT_BUCKET)
   ↓
2. Anonimização Página 1
   - Remove: Nome, CPF, RG, CRM
   - Preserva: Sexo, Data, Hora, Conclusão
   ↓
3. Extração Página 2
   - Renderiza em 300 DPI
   - Aplica tarjas pretas
   - Converte para PNG
   ↓
4. PNG → PDF
   - Mantém dimensões originais
   - Alta qualidade
   ↓
5. Merge
   - Página 1 anonimizada + Página 2 (PNG)
   ↓
6. Compressão ZIP
   - Formato: .pdf.zip
   - ZIP_DEFLATED (compress level 6)
   - PDF interno mantido com nome original
   ↓
7. Upload S3 (OUTPUT_BUCKET)
   - Nome: anonymized_ULID.pdf.zip
   - ContentType: application/zip
   - Metadados: tamanhos original/comprimido
```

## Controle de Concorrência

**Por que MaxConcurrency funciona:**

AWS Step Functions controla nativamente quantas Lambdas executam simultaneamente.

**Sem MaxConcurrency** (problema):
- Invoca 1500 Lambdas ao mesmo tempo
- Excede limite AWS
- Erros de throttling

**Com MaxConcurrency: 500** (solução):
- Invoca 500 Lambdas
- Espera 1 terminar
- Invoca próxima (501)
- Sempre mantém 500 executando

## Performance

### 1.5 Milhões de Arquivos

**Divisão:**
- 1.500.000 arquivos ÷ 200 = 7500 lotes
- 7500 lotes ÷ 500 concurrent = 15 rodadas

**Timeline:**
```
Minuto 0:     Script prepara lotes (1-2 min)
Minuto 2:     Step Function invoca 500 Lambdas
Minuto 2-14:  Primeiras 500 Lambdas processam (~12 min cada)
Minuto 14:    Lambda 1 termina → Lambda 501 inicia
Minuto 15:    Lambda 2 termina → Lambda 502 inicia
...
Hora 3-4:     Todas concluídas
```

**Resultado:**
- Tempo total: 3-4 horas
- Throughput: ~400k arquivos/hora
- Custo: ~$210 USD
- **100% dos PDFs processados** (nenhum fica pendente)

## Garantias

1. **MaxConcurrency respeitado**: Step Functions garante
2. **Retry automático**: 3 tentativas por lote
3. **Idempotência**: Pode executar múltiplas vezes
4. **Qualidade**: 300 DPI, sem perda

## Comandos

```bash
# === LOCALSTACK (Testes) ===
# 1. Iniciar
docker-compose up -d

# 2. Deploy
bash scripts/local/deploy_localstack.sh

# 3. Testar
bash scripts/local/execute_statemachine.sh test_data_local/exemplo.pdf

# === PRODUÇÃO (AWS) ===
# 1. Deploy
bash scripts/production/deploy_production.sh

# 2. Upload PDFs
aws s3 cp pdfs/ s3://bp-ecg-input-prod/ --recursive

# 3. Executar em paralelo
bash scripts/production/execute_parallel.sh

# 4. Monitorar
# Console: https://console.aws.amazon.com/states/
aws stepfunctions list-executions --state-machine-arn <ARN>
```

## Arquivos Principais

```
bp_ecg_etl/
├── s3_handler.py             # Handler S3 events (Lambda entry point)
├── batch_processor.py         # Lógica de processamento em lote
├── pdf_processor.py           # Pipeline completo de PDF
├── pdf_anonymizer.py          # Anonimização de texto
├── ecg_extractor.py           # Extração página 2 como PNG
├── s3_utils.py                # Upload/download com compressão ZIP
└── config.py                  # Configurações centralizadas

scripts/
├── local/
│   ├── deploy_localstack.sh   # Deploy LocalStack
│   ├── execute_statemachine.sh # Testar 1 PDF
│   └── README.md
└── production/
    ├── deploy_production.sh   # Deploy AWS
    ├── execute_parallel.sh     # Processar em massa
    └── README.md

template.yaml                  # Produção (AWS)
template.localstack.yaml       # LocalStack (testes)
statemachine/
├── simple_processor.asl.json    # State Machine simples (1 PDF)
└── parallel_processor.asl.json  # State Machine paralela (massa)
```

**Total: ~400 linhas de código principal**

## Resumo

1. **Simples**: Script local faz preparação
2. **Escalável**: Step Functions gerencia 500 Lambdas
3. **Confiável**: Retry automático + MaxConcurrency
4. **Rápido**: 1.5M arquivos em 7-8 horas
5. **Barato**: ~$210 para 1.5M arquivos
