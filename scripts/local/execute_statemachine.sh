#!/bin/bash
set -e

INPUT_BUCKET="bp-ecg-input"
OUTPUT_BUCKET="bp-ecg-output"
STATE_MACHINE_NAME="bp-ecg-processor"

if [ -z "$1" ]; then
    echo "Usage: bash execute_statemachine.sh <file.pdf>"
    exit 1
fi

PDF_FILE="$1"
PDF_KEY=$(basename "$PDF_FILE")

echo "[INFO] Executing state machine for: $PDF_KEY"

# Upload PDF
if [ -f "$PDF_FILE" ]; then
    echo "[INFO] Uploading file"
    awslocal s3 cp "$PDF_FILE" s3://$INPUT_BUCKET/$PDF_KEY
    echo "[OK] Upload completed: s3://$INPUT_BUCKET/$PDF_KEY"
else
    echo "[ERROR] File not found: $PDF_FILE"
    exit 1
fi

# Get State Machine ARN
echo "[INFO] Getting state machine ARN"
STATE_MACHINE_ARN=$(awslocal stepfunctions list-state-machines \
    --query "stateMachines[?name=='$STATE_MACHINE_NAME'].stateMachineArn" \
    --output text)

if [ -z "$STATE_MACHINE_ARN" ]; then
    echo "[ERROR] State machine not found: $STATE_MACHINE_NAME"
    exit 1
fi

# Create input
INPUT_JSON=$(cat <<EOF
{
  "bucket": "$INPUT_BUCKET",
  "key": "$PDF_KEY"
}
EOF
)

# Execute
echo "[INFO] Starting execution"
EXECUTION_ARN=$(awslocal stepfunctions start-execution \
    --state-machine-arn $STATE_MACHINE_ARN \
    --input "$INPUT_JSON" \
    --query 'executionArn' \
    --output text)

echo "[OK] Execution started"

# Wait for completion
echo "[INFO] Waiting for completion (max 60s)"
COUNTER=0
while [ $COUNTER -lt 30 ]; do
    STATUS=$(awslocal stepfunctions describe-execution \
        --execution-arn $EXECUTION_ARN \
        --query 'status' \
        --output text)
    
    if [ "$STATUS" = "SUCCEEDED" ]; then
        echo "[SUCCESS] Execution completed"
        break
    elif [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "TIMED_OUT" ] || [ "$STATUS" = "ABORTED" ]; then
        echo "[ERROR] Execution failed: $STATUS"
        awslocal stepfunctions describe-execution \
            --execution-arn $EXECUTION_ARN
        exit 1
    fi
    
    echo -n "."
    sleep 2
    COUNTER=$((COUNTER + 1))
done

if [ $COUNTER -eq 30 ]; then
    echo ""
    echo "[WARN] Timeout waiting for completion"
fi

# Check result
echo "[INFO] Checking output"
OUTPUT_KEY="${PDF_KEY%.pdf}_anonimizado.pdf"
OUTPUT_KEY="${OUTPUT_KEY%.PDF}_anonimizado.pdf"

if awslocal s3 ls s3://$OUTPUT_BUCKET/$OUTPUT_KEY > /dev/null 2>&1; then
    echo "[OK] Anonymized PDF created"
    echo "[INFO] Downloading result"
    awslocal s3 cp s3://$OUTPUT_BUCKET/$OUTPUT_KEY resultado_$OUTPUT_KEY
    SIZE=$(du -h resultado_$OUTPUT_KEY | cut -f1)
    echo "[OK] File saved: resultado_$OUTPUT_KEY ($SIZE)"
else
    echo "[WARN] Output file not found"
fi
