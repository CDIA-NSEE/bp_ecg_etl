#!/bin/bash
set -e

TEST_DIR="test_data_local"
INPUT_BUCKET="raw-pdfs"
OUTPUT_BUCKET="anon-pdfs"

if [ ! -d "$TEST_DIR" ]; then
    echo "Error: $TEST_DIR not found"
    exit 1
fi

PDF_COUNT=$(find "$TEST_DIR" -name "*.pdf" | wc -l)
if [ "$PDF_COUNT" -eq 0 ]; then
    echo "Error: No PDFs found in $TEST_DIR"
    exit 1
fi

echo "Starting LocalStack..."
docker compose -f docker-compose.local.yml up -d localstack

echo "Waiting for LocalStack to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:4566/_localstack/health > /dev/null 2>&1; then
        echo "LocalStack is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Error: LocalStack failed to start"
        exit 1
    fi
    sleep 1
done

echo "Creating S3 buckets..."
awslocal s3 mb s3://$INPUT_BUCKET 2>/dev/null || true
awslocal s3 mb s3://$OUTPUT_BUCKET 2>/dev/null || true
awslocal s3 rm s3://$INPUT_BUCKET/ --recursive 2>/dev/null || true

echo "Uploading $PDF_COUNT PDFs to s3://$INPUT_BUCKET"
awslocal s3 sync "$TEST_DIR/" s3://$INPUT_BUCKET/ --exclude "*" --include "*.pdf"

echo "Building Docker image..."
docker build -t bp-ecg-etl:test .

echo "Running processing..."
docker run --rm \
  --network bp_ecg_etl_default \
  -e AWS_ENDPOINT_URL=http://localstack:4566 \
  -e AWS_ACCESS_KEY_ID=test \
  -e AWS_SECRET_ACCESS_KEY=test \
  -e INPUT_BUCKET=$INPUT_BUCKET \
  -e OUTPUT_BUCKET=$OUTPUT_BUCKET \
  -e AWS_REGION=us-east-1 \
  -e MAX_WORKERS=10 \
  -e QUEUE_SIZE=50 \
  bp-ecg-etl:test

echo "Downloading results to test_output/"
mkdir -p test_output
awslocal s3 sync s3://$OUTPUT_BUCKET/ test_output/

echo "Done. Results in test_output/"
