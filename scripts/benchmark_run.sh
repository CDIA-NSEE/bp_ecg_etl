#!/bin/bash
# Benchmark Runner - Executa Docker e coleta métricas de performance

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuração
LOCALSTACK_ENDPOINT="${LOCALSTACK_ENDPOINT:-http://localhost:4566}"
INPUT_BUCKET="${INPUT_BUCKET:-raw-pdfs}"
OUTPUT_BUCKET="${OUTPUT_BUCKET:-anon-pdfs}"
DOCKER_IMAGE="${DOCKER_IMAGE:-bp-ecg-etl:latest}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}BP-ECG ETL - Benchmark${NC}"
echo -e "${BLUE}========================================${NC}"

# Verificar se LocalStack está rodando
echo -e "\n${YELLOW}Verificando LocalStack...${NC}"
if ! curl -s "${LOCALSTACK_ENDPOINT}/_localstack/health" > /dev/null 2>&1; then
    echo -e "${RED}ERRO: LocalStack não está rodando!${NC}"
    echo -e "${YELLOW}   Execute: docker-compose up -d${NC}"
    exit 1
fi
echo -e "${GREEN}LocalStack rodando${NC}"

# Verificar se a imagem Docker existe
echo -e "\n${YELLOW}Verificando imagem Docker...${NC}"
if ! docker images | grep -q "bp-ecg-etl"; then
    echo -e "${RED}ERRO: Imagem Docker não encontrada!${NC}"
    echo -e "${YELLOW}   Execute: docker build -t bp-ecg-etl .${NC}"
    exit 1
fi
echo -e "${GREEN}Imagem Docker encontrada${NC}"

# Contar PDFs no bucket
echo -e "\n${YELLOW}Verificando PDFs no bucket...${NC}"
PDF_COUNT=$(awslocal s3 ls "s3://${INPUT_BUCKET}/batch_test/" --recursive 2>/dev/null | wc -l || echo "0")
echo -e "${GREEN}${PDF_COUNT} PDFs encontrados${NC}"

if [ "$PDF_COUNT" -eq 0 ]; then
    echo -e "${RED}ERRO: Nenhum PDF encontrado!${NC}"
    echo -e "${YELLOW}   Execute: python scripts/benchmark_setup.py${NC}"
    exit 1
fi

# Limpar output bucket antes do teste
echo -e "\n${YELLOW}Limpando bucket de saida...${NC}"
awslocal s3 rm "s3://${OUTPUT_BUCKET}/" --recursive 2>/dev/null || true
echo -e "${GREEN}Bucket limpo${NC}"

# Criar arquivo de log
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="benchmark_${TIMESTAMP}.log"

echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}INICIANDO BENCHMARK${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}PDFs a processar: ${PDF_COUNT}${NC}"
echo -e "${YELLOW}Log: ${LOG_FILE}${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Capturar tempo de início
START_TIME=$(date +%s)

# Executar Docker
docker run --rm \
    --network bridge \
    -e AWS_ACCESS_KEY_ID=test \
    -e AWS_SECRET_ACCESS_KEY=test \
    -e AWS_DEFAULT_REGION=us-east-1 \
    -e AWS_ENDPOINT_URL="http://host.docker.internal:4566" \
    -e INPUT_BUCKET="${INPUT_BUCKET}" \
    -e OUTPUT_BUCKET="${OUTPUT_BUCKET}" \
    -e INPUT_PREFIX="batch_test/" \
    -e MAX_WORKERS=20 \
    -e MAX_PROCESS_WORKERS=4 \
    -e QUEUE_SIZE=50 \
    -e DPI_PAGE2_RENDER=450 \
    -e ZIP_COMPRESSION_LEVEL=5 \
    -e LOG_SAMPLING_RATE=0.5 \
    -e LOG_FORMAT=json \
    --add-host=host.docker.internal:host-gateway \
    "${DOCKER_IMAGE}" 2>&1 | tee "${LOG_FILE}"

# Capturar tempo de fim
END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

# Calcular métricas
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}METRICAS DE PERFORMANCE${NC}"
echo -e "${BLUE}========================================${NC}"

# Contar PDFs processados
PROCESSED_COUNT=$(awslocal s3 ls "s3://${OUTPUT_BUCKET}/" --recursive 2>/dev/null | wc -l || echo "0")

# Calcular estatísticas
MINUTES=$((TOTAL_TIME / 60))
SECONDS=$((TOTAL_TIME % 60))

if [ "$TOTAL_TIME" -gt 0 ]; then
    THROUGHPUT=$(echo "scale=2; $PROCESSED_COUNT / $TOTAL_TIME" | bc)
else
    THROUGHPUT="0"
fi

SUCCESS_RATE=$(echo "scale=1; ($PROCESSED_COUNT * 100) / $PDF_COUNT" | bc)

# Obter tamanhos dos buckets
INPUT_SIZE=$(awslocal s3 ls "s3://${INPUT_BUCKET}/batch_test/" --recursive --summarize 2>/dev/null | grep "Total Size" | awk '{print $3}')
OUTPUT_SIZE=$(awslocal s3 ls "s3://${OUTPUT_BUCKET}/" --recursive --summarize 2>/dev/null | grep "Total Size" | awk '{print $3}')

INPUT_MB=$(echo "scale=2; ${INPUT_SIZE:-0} / 1048576" | bc)
OUTPUT_MB=$(echo "scale=2; ${OUTPUT_SIZE:-0} / 1048576" | bc)

if [ "${INPUT_SIZE:-0}" -gt 0 ]; then
    COMPRESSION=$(echo "scale=1; (1 - $OUTPUT_SIZE / $INPUT_SIZE) * 100" | bc)
else
    COMPRESSION="0"
fi

# Exibir resultados
echo -e "${GREEN}Total de PDFs:${NC}        ${PDF_COUNT}"
echo -e "${GREEN}PDFs Processados:${NC}    ${PROCESSED_COUNT}"
echo -e "${GREEN}Taxa de Sucesso:${NC}     ${SUCCESS_RATE}%"
echo -e ""
echo -e "${GREEN}Tempo Total:${NC}         ${MINUTES}m ${SECONDS}s (${TOTAL_TIME}s)"
echo -e "${GREEN}Throughput:${NC}          ${THROUGHPUT} PDFs/sec"
echo -e ""
echo -e "${GREEN}Tamanho Original:${NC}    ${INPUT_MB} MB"
echo -e "${GREEN}Tamanho Comprimido:${NC}  ${OUTPUT_MB} MB"
echo -e "${GREEN}Compressão:${NC}          ${COMPRESSION}%"
echo -e ""
echo -e "${GREEN}Log salvo em:${NC}        ${LOG_FILE}"

# Salvar métricas em JSON
METRICS_FILE="benchmark_${TIMESTAMP}_metrics.json"
cat > "${METRICS_FILE}" << EOF
{
  "timestamp": "${TIMESTAMP}",
  "total_pdfs": ${PDF_COUNT},
  "processed_pdfs": ${PROCESSED_COUNT},
  "success_rate": ${SUCCESS_RATE},
  "total_time_seconds": ${TOTAL_TIME},
  "throughput_pdfs_per_second": ${THROUGHPUT},
  "input_size_mb": ${INPUT_MB},
  "output_size_mb": ${OUTPUT_MB},
  "compression_ratio": ${COMPRESSION},
  "config": {
    "max_workers": 200,
    "max_process_workers": 16,
    "dpi_page2": 450,
    "zip_level": 5
  }
}
EOF

echo -e "${GREEN}Métricas salvas em:${NC}  ${METRICS_FILE}"

echo -e "\n${BLUE}========================================${NC}"

# Verificar sucesso
if [ "$PROCESSED_COUNT" -eq "$PDF_COUNT" ]; then
    echo -e "${GREEN}BENCHMARK COMPLETO COM SUCESSO!${NC}"
    exit 0
else
    echo -e "${YELLOW}AVISO: BENCHMARK COMPLETO COM FALHAS${NC}"
    echo -e "${YELLOW}   Esperado: ${PDF_COUNT}, Processado: ${PROCESSED_COUNT}${NC}"
    exit 1
fi
