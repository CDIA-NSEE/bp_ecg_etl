#!/bin/bash
set -e

STACK_NAME="${STACK_NAME:-bp-ecg-production}"
INPUT_BUCKET="${INPUT_BUCKET:-bp-ecg-input-prod}"
OUTPUT_BUCKET="${OUTPUT_BUCKET:-bp-ecg-output-prod}"
AWS_REGION="${AWS_REGION:-us-east-1}"
TEMPLATE_FILE="template.yaml"

echo "[INFO] Deploying to AWS Production"
echo "Stack: $STACK_NAME"
echo "Region: $AWS_REGION"
echo "Input Bucket: $INPUT_BUCKET"
echo "Output Bucket: $OUTPUT_BUCKET"
echo ""

# Verify AWS credentials
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "[ERROR] AWS credentials not configured"
    echo "Run: aws configure"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "[OK] AWS Account: $ACCOUNT_ID"

# Create S3 buckets if they don't exist
echo "[INFO] Checking S3 buckets"
if ! aws s3 ls s3://$INPUT_BUCKET 2>/dev/null; then
    echo "[INFO] Creating input bucket: $INPUT_BUCKET"
    aws s3 mb s3://$INPUT_BUCKET --region $AWS_REGION
    aws s3api put-public-access-block \
        --bucket $INPUT_BUCKET \
        --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
    echo "[OK] Input bucket created"
else
    echo "[OK] Input bucket exists"
fi

if ! aws s3 ls s3://$OUTPUT_BUCKET 2>/dev/null; then
    echo "[INFO] Creating output bucket: $OUTPUT_BUCKET"
    aws s3 mb s3://$OUTPUT_BUCKET --region $AWS_REGION
    aws s3api put-public-access-block \
        --bucket $OUTPUT_BUCKET \
        --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
    echo "[OK] Output bucket created"
else
    echo "[OK] Output bucket exists"
fi

# Build with SAM
echo "[INFO] Building SAM application"
sam build --use-container --template $TEMPLATE_FILE

# Deploy with SAM
echo "[INFO] Deploying to AWS"
sam deploy \
    --template-file .aws-sam/build/template.yaml \
    --stack-name $STACK_NAME \
    --region $AWS_REGION \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides \
        InputBucket=$INPUT_BUCKET \
        OutputBucket=$OUTPUT_BUCKET \
    --resolve-s3 \
    --no-fail-on-empty-changeset

echo ""
echo "[SUCCESS] Production deployment completed"
echo ""
echo "Get stack outputs:"
echo "  aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION --query 'Stacks[0].Outputs'"
echo ""
echo "List Lambda functions:"
echo "  aws lambda list-functions --region $AWS_REGION --query 'Functions[?starts_with(FunctionName, \`bp-ecg\`)].FunctionName'"
echo ""
echo "List State Machines:"
echo "  aws stepfunctions list-state-machines --region $AWS_REGION --query 'stateMachines[?starts_with(name, \`bp-ecg\`)].{Name:name,Status:status}' --output table"
