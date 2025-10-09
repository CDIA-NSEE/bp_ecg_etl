#!/bin/bash
set -e

INPUT_BUCKET="${INPUT_BUCKET:-bp-ecg-input-prod}"
OUTPUT_BUCKET="${OUTPUT_BUCKET:-bp-ecg-output-prod}"
STATE_MACHINE_NAME="${STATE_MACHINE_NAME:-bp-ecg-parallel-processor}"
AWS_REGION="${AWS_REGION:-us-east-1}"
BATCH_SIZE=${BATCH_SIZE:-10}
MAX_BATCHES=${MAX_BATCHES:-50}

echo "[INFO] Parallel processing execution (PRODUCTION)"
echo "Region: $AWS_REGION"
echo "Input Bucket: $INPUT_BUCKET"
echo "State Machine: $STATE_MACHINE_NAME"
echo ""

# Verify AWS credentials
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "[ERROR] AWS credentials not configured"
    echo "Run: aws configure"
    exit 1
fi

# List all PDFs in bucket
echo "[INFO] Listing PDFs in s3://$INPUT_BUCKET/"
PDF_LIST=$(aws s3 ls s3://$INPUT_BUCKET/ --region $AWS_REGION | grep -E '\.pdf|\.PDF' | awk '{print $4}' || true)

if [ -z "$PDF_LIST" ]; then
    echo "[ERROR] No PDF files found in bucket"
    exit 1
fi

# Count PDFs
PDF_COUNT=$(echo "$PDF_LIST" | wc -l)
echo "[OK] Found $PDF_COUNT PDF(s)"

# Create batches JSON
echo "[INFO] Creating batches (size: $BATCH_SIZE)"
BATCHES_JSON="{"
BATCHES_JSON+="\"batches\":["

BATCH_NUM=0
CURRENT_BATCH=""
FILE_COUNT=0

while IFS= read -r pdf; do
    if [ -n "$pdf" ]; then
        if [ $FILE_COUNT -eq 0 ]; then
            CURRENT_BATCH="{\"keys\":["
        else
            CURRENT_BATCH+=","
        fi
        
        CURRENT_BATCH+="\"$pdf\""
        FILE_COUNT=$((FILE_COUNT + 1))
        
        if [ $FILE_COUNT -eq $BATCH_SIZE ]; then
            CURRENT_BATCH+="]}"
            
            if [ $BATCH_NUM -gt 0 ]; then
                BATCHES_JSON+=","
            fi
            BATCHES_JSON+="$CURRENT_BATCH"
            
            BATCH_NUM=$((BATCH_NUM + 1))
            FILE_COUNT=0
            CURRENT_BATCH=""
            
            if [ $BATCH_NUM -ge $MAX_BATCHES ]; then
                echo "[WARN] Reached max batches limit ($MAX_BATCHES)"
                break
            fi
        fi
    fi
done <<< "$PDF_LIST"

# Add remaining files
if [ $FILE_COUNT -gt 0 ]; then
    CURRENT_BATCH+="]}"
    if [ $BATCH_NUM -gt 0 ]; then
        BATCHES_JSON+=","
    fi
    BATCHES_JSON+="$CURRENT_BATCH"
    BATCH_NUM=$((BATCH_NUM + 1))
fi

BATCHES_JSON+="]}"

echo "[OK] Created $BATCH_NUM batch(es)"

# Get State Machine ARN
echo "[INFO] Getting state machine ARN"
STATE_MACHINE_ARN=$(aws stepfunctions list-state-machines \
    --region $AWS_REGION \
    --query "stateMachines[?name=='$STATE_MACHINE_NAME'].stateMachineArn" \
    --output text)

if [ -z "$STATE_MACHINE_ARN" ]; then
    echo "[ERROR] State machine not found: $STATE_MACHINE_NAME"
    echo "[INFO] Available state machines:"
    aws stepfunctions list-state-machines --region $AWS_REGION --query 'stateMachines[*].name' --output text
    exit 1
fi

# Execute
echo "[INFO] Starting parallel execution"
echo "[DEBUG] Input: $BATCHES_JSON"

EXECUTION_ARN=$(aws stepfunctions start-execution \
    --region $AWS_REGION \
    --state-machine-arn $STATE_MACHINE_ARN \
    --input "$BATCHES_JSON" \
    --query 'executionArn' \
    --output text)

echo "[OK] Execution started"
echo "Execution ARN: $EXECUTION_ARN"

# Wait for completion
echo "[INFO] Waiting for completion (max 120s)"
COUNTER=0
while [ $COUNTER -lt 60 ]; do
    STATUS=$(aws stepfunctions describe-execution \
        --region $AWS_REGION \
        --execution-arn $EXECUTION_ARN \
        --query 'status' \
        --output text)
    
    if [ "$STATUS" = "SUCCEEDED" ]; then
        echo "[SUCCESS] Parallel execution completed"
        break
    elif [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "TIMED_OUT" ] || [ "$STATUS" = "ABORTED" ]; then
        echo "[ERROR] Execution failed: $STATUS"
        aws stepfunctions describe-execution \
            --region $AWS_REGION \
            --execution-arn $EXECUTION_ARN
        exit 1
    fi
    
    echo -n "."
    sleep 2
    COUNTER=$((COUNTER + 1))
done

if [ $COUNTER -eq 60 ]; then
    echo ""
    echo "[WARN] Timeout waiting for completion"
fi

# Check results
echo "[INFO] Checking output bucket"
OUTPUT_COUNT=$(aws s3 ls s3://$OUTPUT_BUCKET/ --region $AWS_REGION | grep -c '\.pdf' || echo "0")
echo "[OK] Output files: $OUTPUT_COUNT"

# List output files
if [ $OUTPUT_COUNT -gt 0 ]; then
    echo "[INFO] Output files:"
    aws s3 ls s3://$OUTPUT_BUCKET/ --region $AWS_REGION | grep '\.pdf' | awk '{print "  - " $4 " (" $3 ")"}'
fi

echo ""
echo "[SUCCESS] Parallel processing completed"
echo "Processed: $PDF_COUNT PDFs in $BATCH_NUM batch(es)"
echo "Output: $OUTPUT_COUNT anonymized PDFs"
