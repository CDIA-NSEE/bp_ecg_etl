# Fluxo de Processamento Simplificado

## Arquitetura

```
Script Local → Step Functions → 500 Lambdas → S3 Output
```

## Componentes

### 1. Script Local (`prepare_and_deploy.py`)
- Lista PDFs do S3 de entrada
- Divide em lotes de 200 arquivos
- Cria payload JSON com todos os lotes
- Inicia Step Function

### 2. Step Functions
- Recebe array com todos os lotes
- MaxConcurrency: 500
- Invoca Lambda para cada lote
- Garante máximo de 500 execuções simultâneas

### 3. Lambda Processor (`lambda_handler.py`)
- Recebe 1 lote (200 PDFs)
- Processa com 15 workers assíncronos
- Para cada PDF:
  - Download do S3
  - Anonimiza página 1
  - Extrai página 2 como PNG
  - Mescla e comprime
  - Upload para S3 de saída

## Fluxo Passo a Passo

### Execução do Script

```bash
python scripts/prepare_and_deploy.py --bucket bp-ecg-input
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
6. Compressão
   - Deflate (sem perda de qualidade)
   ↓
7. Upload S3 (OUTPUT_BUCKET)
   - Nome: anonymized_ULID.pdf
   - Metadados completos
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
# 1. Deploy
sam build && sam deploy

# 2. Upload PDFs
aws s3 cp pdfs/ s3://bp-ecg-input/ --recursive

# 3. Executar
python scripts/prepare_and_deploy.py --bucket bp-ecg-input

# 4. Monitorar
# Console AWS: https://console.aws.amazon.com/states/
```

## Arquivos Principais

```
bp_ecg_etl/
├── lambda_handler.py          # Lambda simples (50 linhas)
├── batch_processor.py         # Lógica de processamento
├── pdf_processor.py           # Pipeline PDF
├── pdf_anonymizer.py          # Anonimização
└── s3_utils.py               # Upload/download

scripts/
└── prepare_and_deploy.py     # Script de execução (130 linhas)

template.yaml                  # Configuração AWS (47 linhas)
statemachine/
└── parallel_processor.asl.json # Step Function
```

**Total: ~400 linhas de código principal**

## Resumo

1. **Simples**: Script local faz preparação
2. **Escalável**: Step Functions gerencia 500 Lambdas
3. **Confiável**: Retry automático + MaxConcurrency
4. **Rápido**: 1.5M arquivos em 7-8 horas
5. **Barato**: ~$210 para 1.5M arquivos
