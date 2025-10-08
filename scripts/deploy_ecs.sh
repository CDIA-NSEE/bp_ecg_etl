#!/bin/bash
set -e

# BP-ECG ETL - ECS Fargate Deployment Script
# This script builds, pushes, and deploys the ECS Fargate task

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   BP-ECG ETL - ECS Fargate Deployment                         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
ECR_REPO_NAME="bp-ecg-etl"
IMAGE_TAG="${IMAGE_TAG:-latest}"
CLUSTER_NAME="bp-ecg-cluster"
SERVICE_NAME="bp-ecg-processor"
TASK_FAMILY="bp-ecg-processor"

# S3 Buckets
INPUT_BUCKET="${INPUT_BUCKET:-raw-pdfs}"
OUTPUT_BUCKET="${OUTPUT_BUCKET:-anon-pdfs}"

# ECS Configuration
TASK_CPU="${TASK_CPU:-16384}"      # 16 vCPUs
TASK_MEMORY="${TASK_MEMORY:-32768}" # 32 GB
MAX_WORKERS="${MAX_WORKERS:-50}"

# VPC Configuration (customize for your environment)
VPC_ID="${VPC_ID:-}"
SUBNET_IDS="${SUBNET_IDS:-}"
SECURITY_GROUP_ID="${SECURITY_GROUP_ID:-}"

echo "[1/10] Validating prerequisites..."
echo "  ✓ AWS Region: $AWS_REGION"
echo "  ✓ AWS Account: $AWS_ACCOUNT_ID"

# Check required tools
command -v docker >/dev/null 2>&1 || { echo "  ✗ Docker not found. Install Docker first."; exit 1; }
command -v aws >/dev/null 2>&1 || { echo "  ✗ AWS CLI not found. Install AWS CLI first."; exit 1; }
echo "  ✓ Required tools available"

echo ""
echo "[2/10] Creating ECR repository..."
if ! aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION >/dev/null 2>&1; then
    aws ecr create-repository \
        --repository-name $ECR_REPO_NAME \
        --region $AWS_REGION \
        --image-scanning-configuration scanOnPush=true \
        --encryption-configuration encryptionType=AES256 >/dev/null
    echo "  ✓ ECR repository created: $ECR_REPO_NAME"
else
    echo "  ✓ ECR repository already exists: $ECR_REPO_NAME"
fi

ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME"

echo ""
echo "[3/10] Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $ECR_URI >/dev/null 2>&1
echo "  ✓ Logged in to ECR"

echo ""
echo "[4/10] Building Docker image..."
docker build -t $ECR_REPO_NAME:$IMAGE_TAG . --quiet
echo "  ✓ Docker image built: $ECR_REPO_NAME:$IMAGE_TAG"

echo ""
echo "[5/10] Tagging and pushing image to ECR..."
docker tag $ECR_REPO_NAME:$IMAGE_TAG $ECR_URI:$IMAGE_TAG
docker push $ECR_URI:$IMAGE_TAG --quiet
echo "  ✓ Image pushed to: $ECR_URI:$IMAGE_TAG"

echo ""
echo "[6/10] Creating/updating S3 buckets..."
for bucket in $INPUT_BUCKET $OUTPUT_BUCKET; do
    if ! aws s3 ls "s3://$bucket" >/dev/null 2>&1; then
        aws s3 mb "s3://$bucket" --region $AWS_REGION >/dev/null
        echo "  ✓ Created bucket: $bucket"
    else
        echo "  ✓ Bucket exists: $bucket"
    fi
done

echo ""
echo "[7/10] Creating ECS cluster..."
if ! aws ecs describe-clusters --clusters $CLUSTER_NAME --region $AWS_REGION --query 'clusters[0].status' --output text 2>/dev/null | grep -q ACTIVE; then
    aws ecs create-cluster \
        --cluster-name $CLUSTER_NAME \
        --region $AWS_REGION \
        --capacity-providers FARGATE FARGATE_SPOT \
        --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 \
        >/dev/null
    echo "  ✓ ECS cluster created: $CLUSTER_NAME"
else
    echo "  ✓ ECS cluster exists: $CLUSTER_NAME"
fi

echo ""
echo "[8/10] Creating CloudWatch log group..."
LOG_GROUP="/ecs/$TASK_FAMILY"
if ! aws logs describe-log-groups --log-group-name-prefix $LOG_GROUP --region $AWS_REGION --query 'logGroups[0].logGroupName' --output text 2>/dev/null | grep -q "$LOG_GROUP"; then
    aws logs create-log-group --log-group-name $LOG_GROUP --region $AWS_REGION >/dev/null
    echo "  ✓ Log group created: $LOG_GROUP"
else
    echo "  ✓ Log group exists: $LOG_GROUP"
fi

echo ""
echo "[9/10] Creating/updating task definition..."

# Generate task definition with current values
cat > task-definition-deploy.json <<EOF
{
  "family": "$TASK_FAMILY",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "$TASK_CPU",
  "memory": "$TASK_MEMORY",
  "executionRoleArn": "arn:aws:iam::$AWS_ACCOUNT_ID:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::$AWS_ACCOUNT_ID:role/bp-ecg-task-role",
  "containerDefinitions": [
    {
      "name": "bp-ecg-processor",
      "image": "$ECR_URI:$IMAGE_TAG",
      "essential": true,
      "environment": [
        {"name": "INPUT_BUCKET", "value": "$INPUT_BUCKET"},
        {"name": "OUTPUT_BUCKET", "value": "$OUTPUT_BUCKET"},
        {"name": "AWS_REGION", "value": "$AWS_REGION"},
        {"name": "MAX_WORKERS", "value": "$MAX_WORKERS"},
        {"name": "QUEUE_SIZE", "value": "200"},
        {"name": "DPI_PAGE2_RENDER", "value": "150"},
        {"name": "LINE_TOLERANCE", "value": "1.0"},
        {"name": "PREVLINE_TOLERANCE", "value": "10.0"},
        {"name": "PADDING", "value": "1.0"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "$LOG_GROUP",
          "awslogs-region": "$AWS_REGION",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
EOF

TASK_DEF_ARN=$(aws ecs register-task-definition \
    --cli-input-json file://task-definition-deploy.json \
    --region $AWS_REGION \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

echo "  ✓ Task definition registered: $TASK_DEF_ARN"
rm task-definition-deploy.json

echo ""
echo "[10/10] Deployment complete!"
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   Deployment Summary                                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "  Cluster:        $CLUSTER_NAME"
echo "  Task Family:    $TASK_FAMILY"
echo "  Image:          $ECR_URI:$IMAGE_TAG"
echo "  CPU:            $TASK_CPU (16 vCPUs)"
echo "  Memory:         $TASK_MEMORY MB (32 GB)"
echo "  Max Workers:    $MAX_WORKERS"
echo "  Input Bucket:   s3://$INPUT_BUCKET"
echo "  Output Bucket:  s3://$OUTPUT_BUCKET"
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   Run Task                                                     ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "To run the task (requires VPC configuration):"
echo ""
echo "aws ecs run-task \\"
echo "  --cluster $CLUSTER_NAME \\"
echo "  --task-definition $TASK_FAMILY \\"
echo "  --launch-type FARGATE \\"
echo "  --network-configuration \"awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}\" \\"
echo "  --region $AWS_REGION"
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   Monitor Logs                                                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "aws logs tail $LOG_GROUP --follow --region $AWS_REGION"
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   Performance Estimates (1.5M PDFs)                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "  Throughput:     ~33 PDFs/second (50 workers)"
echo "  Total Time:     ~12-14 hours (continuous processing)"
echo "  Cost Estimate:  ~\$8-10 (Fargate pricing)"
echo ""
echo "✨ Ready to process 1.5 million PDFs! ✨"
