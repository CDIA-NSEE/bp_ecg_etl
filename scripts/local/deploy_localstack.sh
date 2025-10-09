#!/bin/bash
set -e

STACK_NAME="bp-ecg-stack"
INPUT_BUCKET="bp-ecg-input"
OUTPUT_BUCKET="bp-ecg-output"
TEST_DATA_DIR="./test_data_local"

echo "[INFO] Deploying to LocalStack using SAM"

# Check LocalStack
if ! curl -s http://localhost:4566/_localstack/health > /dev/null; then
    echo "[ERROR] LocalStack not running"
    echo "Run: docker-compose up -d"
    exit 1
fi
echo "[OK] LocalStack is running"

# Create S3 buckets
echo "[INFO] Creating S3 buckets"
awslocal s3 mb s3://$INPUT_BUCKET 2>/dev/null || echo "[WARN] Bucket $INPUT_BUCKET already exists"
awslocal s3 mb s3://$OUTPUT_BUCKET 2>/dev/null || echo "[WARN] Bucket $OUTPUT_BUCKET already exists"

# Upload test PDFs
if [ -d "$TEST_DATA_DIR" ]; then
    echo "[INFO] Uploading test PDFs from $TEST_DATA_DIR"
    PDF_COUNT=0
    for pdf in "$TEST_DATA_DIR"/*.pdf "$TEST_DATA_DIR"/*.PDF; do
        if [ -f "$pdf" ]; then
            awslocal s3 cp "$pdf" s3://$INPUT_BUCKET/
            PDF_COUNT=$((PDF_COUNT + 1))
            echo "  - $(basename "$pdf")"
        fi
    done
    echo "[OK] Uploaded $PDF_COUNT test PDFs"
else
    echo "[WARN] Test data directory not found: $TEST_DATA_DIR"
fi

# Build with SAM
echo "[INFO] Building SAM application"
sam build --use-container --template template.localstack.yaml

# Deploy with SAM
echo "[INFO] Deploying to LocalStack"
samlocal deploy \
    --template-file .aws-sam/build/template.yaml \
    --stack-name $STACK_NAME \
    --region us-east-1 \
    --resolve-s3 \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides \
        InputBucket=$INPUT_BUCKET \
        OutputBucket=$OUTPUT_BUCKET

echo ""
echo "[SUCCESS] Deployment completed"
echo "Stack: $STACK_NAME"
echo ""
echo "List uploaded PDFs:"
echo "  awslocal s3 ls s3://$INPUT_BUCKET/"
echo ""
echo "Get stack outputs:"
echo "  awslocal cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].Outputs'"
