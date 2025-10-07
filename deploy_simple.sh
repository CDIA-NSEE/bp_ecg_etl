#!/bin/bash
# Deploy Lambda function to LocalStack

set -e

# Configuration
FUNCTION_NAME="bp-ecg-etl-anonymizer"
HANDLER="bp_ecg_etl.main.lambda_handler"
RUNTIME="python3.12"
LOCALSTACK_ENDPOINT="http://localhost:4566"
INPUT_BUCKET="raw-pdfs"
OUTPUT_BUCKET="anon-pdfs"

# AWS credentials for LocalStack
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

echo "[1/5] Creating Lambda package..."

# Create temporary directory
TEMP_DIR=$(mktemp -d)
ZIP_FILE="$TEMP_DIR/lambda-function.zip"

# Copy source code
cp -r bp_ecg_etl "$TEMP_DIR/"

# Install dependencies with UV from pyproject.toml
echo "[2/5] Installing dependencies with UV..."
uv pip install --no-deps --target "$TEMP_DIR/" \
    aioboto3==15.0.0 \
    aiobotocore==2.23.0 \
    boto3==1.38.27 \
    botocore==1.38.27 \
    pillow==11.3.0 \
    pymupdf \
    structlog==25.4.0 \
    ulid-py==1.1.0 \
    pydantic==2.11.7 \
    pydantic-core==2.33.2 \
    typing-extensions==4.14.1 \
    annotated-types==0.7.0 \
    python-dotenv==1.1.1

# Create ZIP package
cd "$TEMP_DIR"
zip -r lambda-function.zip . -q
cd - > /dev/null

echo "[3/5] Creating S3 buckets..."
aws s3 mb s3://$INPUT_BUCKET --endpoint-url $LOCALSTACK_ENDPOINT 2>/dev/null || true
aws s3 mb s3://$OUTPUT_BUCKET --endpoint-url $LOCALSTACK_ENDPOINT 2>/dev/null || true

echo "[4/5] Deploying Lambda function..."

# Environment variables
ENV_FILE="$TEMP_DIR/env.json"
cat > "$ENV_FILE" << EOF
{
  "Variables": {
    "INPUT_BUCKET": "$INPUT_BUCKET",
    "OUTPUT_BUCKET": "$OUTPUT_BUCKET",
    "AWS_REGION": "us-east-1",
    "DPI_PAGE2_RENDER": "150",
    "LINE_TOLERANCE": "5",
    "PREVLINE_TOLERANCE": "20",
    "PADDING": "2"
  }
}
EOF

# Deploy or update function
if aws lambda get-function --function-name $FUNCTION_NAME --endpoint-url $LOCALSTACK_ENDPOINT >/dev/null 2>&1; then
    echo "  Updating existing function..."
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://$ZIP_FILE \
        --endpoint-url $LOCALSTACK_ENDPOINT >/dev/null
    
    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --timeout 900 \
        --memory-size 10240 \
        --environment file://$ENV_FILE \
        --endpoint-url $LOCALSTACK_ENDPOINT >/dev/null
else
    echo "  Creating new function..."
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime $RUNTIME \
        --role arn:aws:iam::000000000000:role/lambda-role \
        --handler $HANDLER \
        --zip-file fileb://$ZIP_FILE \
        --timeout 900 \
        --memory-size 10240 \
        --environment file://$ENV_FILE \
        --endpoint-url $LOCALSTACK_ENDPOINT >/dev/null
fi

echo "[5/5] Configuring S3 trigger..."

# Add Lambda permission
aws lambda add-permission \
    --function-name $FUNCTION_NAME \
    --statement-id s3-trigger \
    --action lambda:InvokeFunction \
    --principal s3.amazonaws.com \
    --source-arn "arn:aws:s3:::$INPUT_BUCKET" \
    --endpoint-url $LOCALSTACK_ENDPOINT 2>/dev/null || true

# Configure S3 notification
NOTIF_FILE="/tmp/s3-notification.json"
cat > "$NOTIF_FILE" << EOF
{
  "LambdaFunctionConfigurations": [
    {
      "Id": "bp-ecg-etl-trigger",
      "LambdaFunctionArn": "arn:aws:lambda:us-east-1:000000000000:function:$FUNCTION_NAME",
      "Events": ["s3:ObjectCreated:*"]
    }
  ]
}
EOF

aws s3api put-bucket-notification-configuration \
    --bucket $INPUT_BUCKET \
    --notification-configuration file://$NOTIF_FILE \
    --endpoint-url $LOCALSTACK_ENDPOINT 2>/dev/null || true

# Cleanup
rm -f "$NOTIF_FILE"
rm -rf "$TEMP_DIR"

echo ""
echo "Deploy completed successfully!"
echo ""
echo "Function: $FUNCTION_NAME"
echo "Runtime: $RUNTIME (900s timeout, 3GB memory)"
echo "Input:   s3://$INPUT_BUCKET/"
echo "Output:  s3://$OUTPUT_BUCKET/"
echo ""
echo "Test with:"
echo "  aws s3 cp example.pdf s3://$INPUT_BUCKET/ --endpoint-url $LOCALSTACK_ENDPOINT"
echo "  aws s3 ls s3://$OUTPUT_BUCKET/ --endpoint-url $LOCALSTACK_ENDPOINT"
echo ""
