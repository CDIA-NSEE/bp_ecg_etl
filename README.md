# BP-ECG ETL

**High-performance PDF anonymization pipeline** for ECG medical documents. Runs on **AWS ECS Fargate** or **AWS Lambda** for scalable, automated processing.

> 🚀 **NEW**: ECS Fargate support for processing millions of PDFs! See [ECS_VS_LAMBDA.md](./ECS_VS_LAMBDA.md) for comparison.

## 🎯 Quick Stats

| Metric | Value |
|--------|-------|
| **Throughput** | 33 PDFs/second (ECS, 50 workers) |
| **Time for 1.5M PDFs** | 12-14 hours (ECS) |
| **Cost per 1.5M PDFs** | ~$9.48 (ECS Fargate) |
| **Compression** | ~35% reduction (GZIP) |

## Features

- **Selective Anonymization**: Removes PII (name, CPF, RG, CRM) while preserving clinical data
- **Intelligent Processing**: Different strategies for single-page vs multi-page PDFs
- **Unique Filenames**: ULID-based naming to prevent conflicts
- **S3 Integration**: Automatic processing triggered by S3 uploads
- **Structured Logging**: JSON logs with structlog
- **Local Testing**: Full LocalStack support

## Prerequisites

- Docker and docker-compose
- AWS CLI
- UV package manager
- Python 3.12+

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Start LocalStack
docker-compose up -d
```

## Development Setup

Install all dependencies (including dev tools):

```bash
# Install project dependencies
uv pip install -e ".[dev]"

# Or install in a virtual environment
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Quick Start

### Option 1: ECS Fargate (Recommended for Large-Scale)

**Best for**: Processing millions of PDFs (1M+), batch jobs, long-running tasks

```bash
# 1. Deploy ECS infrastructure
./deploy_ecs.sh

# 2. Run task (processes ALL unprocessed PDFs until complete)
aws ecs run-task \
  --cluster bp-ecg-cluster \
  --task-definition bp-ecg-processor \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"

# 3. Monitor logs
aws logs tail /ecs/bp-ecg-processor --follow
```

**Features**:
- ⚡ 50 parallel workers (vs 10-20 in Lambda)
- 🕐 Unlimited runtime (vs 15 min in Lambda)
- 💰 ~50% cheaper for large batches
- 🔄 Stream processing with automatic skip of already-processed PDFs
- 📦 Hive-partitioned output: `year=2025/month=01/day=15/anonymized_ULID.pdf.gz`
- 🗜️ GZIP compression (~35% size reduction)

### Option 2: Lambda (LocalStack)

**Best for**: Event-driven processing, small batches (<1000 PDFs)

```bash
./deploy_simple.sh
```

## Deployment Comparison

| Feature | Lambda | ECS Fargate |
|---------|--------|-------------|
| **Setup Time** | 5 min | 15 min |
| **Best For** | Event-driven, <1K PDFs | Batch processing, 1M+ PDFs |
| **Cost (1.5M PDFs)** | ~$17 | ~$9 |
| **Time (1.5M PDFs)** | 31-62 hours | 12-14 hours |
| **Complexity** | Medium | Low |

📖 **Detailed comparison**: See [ECS_VS_LAMBDA.md](./ECS_VS_LAMBDA.md)

## Local Testing

### Quick Start

```bash
# 1. Start LocalStack with S3
./scripts/start_localstack.sh

# 2. Test pipeline with a PDF
python scripts/test_local.py test_data/exemplo1.pdf

# 3. Stop LocalStack
docker-compose down
```

📖 **Complete guide**: See [README_LOCAL_TESTING.md](./README_LOCAL_TESTING.md)

### Manual Testing

```bash
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

# Upload PDF to LocalStack
aws s3 cp example.pdf s3://raw-pdfs/ --endpoint-url http://localhost:4566

# Check anonymized output
aws s3 ls s3://anon-pdfs/ --endpoint-url http://localhost:4566
```

### Automated Tests

```bash
# Unit tests (fast)
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# All tests with coverage
pytest --cov=bp_ecg_etl --cov-report=html
```

## Project Structure

```
bp_ecg_etl/
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions CI/CD
├── bp_ecg_etl/               # Main package
│   ├── __init__.py
│   ├── config.py             # Environment configuration
│   ├── constants.py          # Anonymization constants
│   ├── logging_config.py     # Structured logging
│   ├── main.py               # ECS entry point
│   ├── metrics.py            # CloudWatch metrics
│   ├── models.py             # Domain models
│   ├── pdf_anonymizer.py     # Core anonymization
│   ├── s3_utils.py           # S3 utilities
│   └── validators.py         # Input validation
├── scripts/                  # Utility scripts
│   ├── deploy_ecs.sh         # ECS deployment
│   ├── start_localstack.sh   # Start local environment
│   ├── test_local.py         # Local pipeline test
│   └── test_pdf.py           # Simple PDF test
├── tests/                    # Test suite
│   ├── integration/          # Integration tests
│   └── unit/                 # Unit tests
├── docker-compose.yml        # LocalStack + S3
├── Dockerfile                # Container image
├── pyproject.toml            # Project config
└── README_LOCAL_TESTING.md   # Local testing guide
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|--------|
| `INPUT_BUCKET` | S3 input bucket | `raw-pdfs` |
| `OUTPUT_BUCKET` | S3 output bucket | `anon-pdfs` |
| `AWS_REGION` | AWS region | `us-east-1` |
| `MAX_WORKERS` | Concurrent workers (ECS: 50, Lambda: 10-20) | `50` |
| `QUEUE_SIZE` | asyncio.Queue buffer size | `200` |
| `DPI_PAGE2_RENDER` | DPI for page 2 rendering | `150` |
| `LINE_TOLERANCE` | Line detection tolerance | `1.0` |
| `PREVLINE_TOLERANCE` | Previous line tolerance | `10.0` |
| `PADDING` | Redaction padding | `1.0` |

### Lambda Configuration

- **Runtime**: Python 3.12
- **Memory**: 10GB (10,240 MB) - AWS maximum
- **Timeout**: 900s (15 minutes) - AWS maximum
- **Handler**: `bp_ecg_etl.main.lambda_handler`
- **Workers**: 10-20 (limited by memory)

### ECS Fargate Configuration

- **CPU**: 16 vCPUs (16,384 units)
- **Memory**: 32 GB (32,768 MB) - configurable up to 120 GB
- **Runtime**: Unlimited (runs until completion)
- **Workers**: 50 concurrent (configurable via `MAX_WORKERS`)
- **Container Image**: Multi-stage Docker build with Python 3.12-slim
- **Networking**: AWS VPC with public IP or NAT Gateway for S3 access

**Output Structure**: Hive-partitioned with compression
```
output-bucket/
└── year=2025/
    └── month=01/
        └── day=15/
            └── anonymized_01HXX123.pdf.gz
```

## Development

### Available Tasks (via taskipy)

```bash
# Format code
task format

# Lint code
task lint

# Lint and auto-fix
task lint-fix

# Type check with mypy
task type-check

# Run tests
task test

# Run tests with coverage
task test-cov

# Run all checks (format + lint + type-check)
task check-all

# Pre-commit hook (format + fix + type-check)
task pre-commit
```

### Manual Commands

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Type check
uv run mypy bp_ecg_etl/
```

## Anonymization Rules

### Data Removed

- Patient name (Nome)
- CPF (tax ID)
- RG (national ID)
- Medical registration (CRM)
- Doctor name
- Age (Idade)
- Health insurance (Convênio)

### Data Preserved

- Sex (Sexo)
- Exam date and time
- Heart rate (Frequência cardíaca)
- PR interval
- QRS duration
- QT/QTc interval
- Axis (Eixo P-QRS-T)
- Medical interpretation

### Processing Strategy

- **Single-page PDFs**: Text-based redaction only (preserves vector quality)
- **Multi-page PDFs**: Text redaction on page 1, coordinate-based redaction on rasterized page 2

## Dependencies

All dependencies are managed via `pyproject.toml` with pinned versions for reproducibility.

### Core Dependencies

- **aioboto3==15.0.0**: Async S3 operations
- **boto3==1.38.27**: AWS SDK
- **pillow==11.3.0**: Image processing
- **pymupdf**: PDF manipulation
- **structlog==25.4.0**: Structured logging
- **ulid-py==1.1.0**: Unique filename generation
- **pydantic==2.11.7**: Configuration validation

### Dev Dependencies

- **ruff**: Fast Python linter and formatter
- **mypy**: Static type checker
- **pytest**: Testing framework
- **taskipy**: Task runner

### Installation

```bash
# Production dependencies only
uv pip install .

# Development dependencies
uv pip install -e ".[dev]"
```

## License

MIT License - see LICENSE file for details.
