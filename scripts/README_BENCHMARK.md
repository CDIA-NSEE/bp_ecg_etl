# Guia de Benchmark - BP-ECG ETL

## Objetivo

Testar a performance do pipeline processando **700 PDFs** no LocalStack e medir:
- Tempo total de processamento
- Throughput (PDFs/segundo)
- Taxa de sucesso
- Compressão obtida

---

## Pre-requisitos

1. **LocalStack rodando:**
```bash
docker-compose up -d
```

2. **Imagem Docker buildada:**
```bash
docker build -t bp-ecg-etl .
```

3. **Dependências Python:**
```bash
pip install boto3
```

---

## Como Executar

### Passo 1: Setup (Criar e Subir 700 PDFs)

```bash
python scripts/benchmark_setup.py
```

**O que faz:**
- Cria buckets `raw-pdfs` e `anon-pdfs` no LocalStack
- Limpa buckets existentes
- Gera 700 cópias do PDF `test_data/exemplo1.pdf`
- Faz upload para `s3://raw-pdfs/batch_test/`
- Verifica que tudo está pronto

**Saída esperada:**
```
BP-ECG ETL - Benchmark Setup
Configurando buckets...
PDF fonte: test_data/exemplo1.pdf (145.3 KB)
Gerando e fazendo upload de 700 copias...
  - 700/700 PDFs (50.2 PDFs/sec)

Upload completo!
   Tempo: 13.94s
   Total: 99.3 MB
```

---

### Passo 2: Executar Benchmark

```bash
./scripts/benchmark_run.sh
```

**O que faz:**
- Verifica LocalStack e imagem Docker
- Limpa bucket de saída
- Executa o container Docker com configurações otimizadas
- Coleta métricas em tempo real
- Salva logs e métricas em JSON

**Configurações usadas:**
```
MAX_WORKERS=200
MAX_PROCESS_WORKERS=16
QUEUE_SIZE=800
DPI_PAGE2_RENDER=450
ZIP_COMPRESSION_LEVEL=5
LOG_SAMPLING_RATE=0.1
```

**Saída esperada:**
```
BP-ECG ETL - Benchmark
========================================
INICIANDO BENCHMARK
========================================
PDFs a processar: 700
Log: benchmark_20251016_203000.log
========================================

[logs do processamento...]

========================================
METRICAS DE PERFORMANCE
========================================
Total de PDFs:        700
PDFs Processados:     700
Taxa de Sucesso:      100.0%

Tempo Total:         45m 20s (2720s)
Throughput:          0.26 PDFs/sec

Tamanho Original:    99.30 MB
Tamanho Comprimido:  68.51 MB
Compressao:          31.0%

BENCHMARK COMPLETO COM SUCESSO!
```

---

## Arquivos Gerados

Após o benchmark, você terá:

1. **Log completo:**
   - `benchmark_YYYYMMDD_HHMMSS.log`
   - Todos os logs do Docker em tempo real

2. **Métricas JSON:**
   - `benchmark_YYYYMMDD_HHMMSS_metrics.json`
   - Estatísticas estruturadas em JSON

**Exemplo do JSON:**
```json
{
  "timestamp": "20251016_203000",
  "total_pdfs": 700,
  "processed_pdfs": 700,
  "success_rate": 100.0,
  "total_time_seconds": 2720,
  "throughput_pdfs_per_second": 0.26,
  "input_size_mb": 99.30,
  "output_size_mb": 68.51,
  "compression_ratio": 31.0,
  "config": {
    "max_workers": 200,
    "max_process_workers": 16,
    "dpi_page2": 450,
    "zip_level": 5
  }
}
```

---

## Customizacoes

### Usar outro PDF fonte

Edite `benchmark_setup.py`:
```python
SOURCE_PDF = "test_data/exemplo5.pdf"  # Trocar aqui
```

### Mudar número de PDFs

Edite `benchmark_setup.py`:
```python
NUM_COPIES = 1000  # Trocar de 700 para 1000
```

### Testar configurações diferentes

Edite `benchmark_run.sh`:
```bash
-e MAX_WORKERS=100 \           # Reduzir workers
-e DPI_PAGE2_RENDER=300 \      # Reduzir DPI (mais rápido)
-e ZIP_COMPRESSION_LEVEL=3 \   # Compressão mais rápida
```

---

## Troubleshooting

### LocalStack não conecta

```bash
# Verificar se está rodando
docker ps | grep localstack

# Ver logs
docker-compose logs localstack

# Reiniciar
docker-compose restart localstack
```

### Docker não encontra LocalStack

O script usa `--add-host=host.docker.internal:host-gateway` para o Docker acessar o host.

Se não funcionar, use IP direto:
```bash
LOCALSTACK_ENDPOINT="http://172.17.0.1:4566"
```

### "Nenhum PDF encontrado"

Execute o setup novamente:
```bash
python scripts/benchmark_setup.py
```

---

## Metricas Esperadas

Com as configurações padrão (DPI 450, ZIP 5, 8 vCPUs):

| PDFs | Tempo Estimado | Throughput |
|------|----------------|------------|
| 100  | ~6 min         | 0.26/s     |
| 700  | ~45 min        | 0.26/s     |
| 1000 | ~64 min        | 0.26/s     |

---

## Proximos Passos

Após o benchmark:

1. **Comparar configurações:**
   - Teste DPI 300 vs 450
   - Teste ZIP 3 vs 5
   - Teste diferentes MAX_PROCESS_WORKERS

2. **Análise de logs:**
   - Busque por "Failed" nos logs
   - Verifique queue_size para identificar gargalos

3. **Otimizar baseado nos resultados:**
   - Se CPU < 80%: aumentar MAX_PROCESS_WORKERS
   - Se memória alta: reduzir QUEUE_SIZE
   - Se S3 lento: aumentar S3_MAX_POOL_CONNECTIONS

---

## Comandos Uteis

```bash
# Ver PDFs no bucket input
aws --endpoint-url=http://localhost:4566 s3 ls s3://raw-pdfs/batch_test/ --recursive

# Ver PDFs processados
aws --endpoint-url=http://localhost:4566 s3 ls s3://anon-pdfs/ --recursive

# Baixar um PDF processado
aws --endpoint-url=http://localhost:4566 s3 cp s3://anon-pdfs/2025/01/anonymized_XXXX.pdf.zip ./

# Limpar tudo
aws --endpoint-url=http://localhost:4566 s3 rm s3://raw-pdfs/ --recursive
aws --endpoint-url=http://localhost:4566 s3 rm s3://anon-pdfs/ --recursive
```
