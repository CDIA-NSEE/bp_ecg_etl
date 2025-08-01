# BP-ECG ETL Pipeline

A simplified, asynchronous ETL pipeline for processing PDF documents from S3, extracting text and images, and storing results as Parquet files.

## Features

- **Async Processing**: High-performance PDF processing with controlled concurrency
- **Retry Logic**: Automatic retries for S3 operations with exponential backoff
- **Structured Logging**: JSON logs with contextual information
- **Type Safety**: Full type hints for better maintainability
- **Environment Config**: Simple environment variable configuration
- **Batch Processing**: Efficient batch processing with Lambda self-invocation

## How It Works

1. **Lambda Invocation**: Receives batch parameters (start_after, batch_id)
2. **List PDFs**: Gets PDF objects from S3 source bucket
3. **Process Batch**: Processes PDFs concurrently (configurable limit)
4. **For Each PDF**:
   - Downloads from S3
   - Extracts text from first page
   - Crops images from second page
   - Uploads cropped images to destination bucket
5. **Save Results**: Stores batch results as Parquet file
6. **Next Batch**: Self-invokes Lambda for next batch if more PDFs exist

## Configuration

### Environment Variables

```bash
# AWS Configuration
SOURCE_BUCKET=your-source-bucket
DEST_BUCKET=your-dest-bucket
PDF_PREFIX=pdfs/
IMAGE_PREFIX=images/
METADATA_PREFIX=metadata/
AWS_LAMBDA_FUNCTION_NAME=your-function-name
AWS_REGION=us-east-1

# Processing Configuration
BATCH_SIZE=100
CONCURRENCY=20
IMAGE_DPI=100
IMAGE_QUALITY=85

# Retry Configuration
RETRY_MAX_ATTEMPTS=3
RETRY_INITIAL_WAIT=1.0
RETRY_MAX_WAIT=60.0

# Logging
LOG_LEVEL=INFO
```

### Crop Regions

Crop regions are currently hardcoded but can be made configurable:

```python
crop_regions = [
    CropRegion(x0=100, y0=100, x1=300, y1=300)  # Example crop region
]
```

## Dependencies

- **aioboto3**: Async AWS SDK
- **boto3**: AWS SDK for Lambda invocation
- **pymupdf**: PDF processing and image extraction
- **pillow**: Image processing and JPEG conversion
- **polars**: Fast DataFrame operations and Parquet I/O
- **pydantic**: Configuration validation and type checking
- **structlog**: Structured logging
- **tenacity**: Retry logic with exponential backoff

## Usage

### Local Development

```bash
# Install dependencies
pip install -e .

# Set environment variables
export SOURCE_BUCKET=test-source-bucket
export DEST_BUCKET=test-dest-bucket
# ... other variables

# Run locally (for testing)
python -c "from src.main import lambda_handler; print(lambda_handler({}, None))"
```

### Lambda Deployment

1. Package the code with dependencies
2. Deploy to AWS Lambda
3. Set environment variables
4. Configure appropriate IAM permissions for S3 and Lambda

### Required IAM Permissions

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-source-bucket",
                "arn:aws:s3:::your-source-bucket/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject"
            ],
            "Resource": [
                "arn:aws:s3:::your-dest-bucket/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "lambda:InvokeFunction"
            ],
            "Resource": "arn:aws:lambda:region:account:function:your-function-name"
        }
    ]
}
```

## Monitoring and Logging

The pipeline uses structured logging with contextual information:

```json
{
    "timestamp": "2024-01-15T10:30:00Z",
    "level": "info",
    "event": "PDF processing completed",
    "batch_id": 1,
    "file_id": "document_123",
    "processing_time_ms": 1500,
    "images_extracted": 3
}
```

## Error Handling

- **Retryable Errors**: Automatically retried with exponential backoff
- **Non-Retryable Errors**: Logged and marked as failed
- **Partial Failures**: Individual PDF failures don't stop batch processing
- **Graceful Degradation**: Missing pages or crop failures are handled gracefully

## Performance Considerations

- **Concurrency Control**: Semaphore limits concurrent PDF processing
- **Memory Management**: Streaming S3 operations and proper resource cleanup
- **Batch Size**: Configurable batch size for optimal Lambda execution time
- **Async Operations**: Non-blocking I/O for better resource utilization

## Development

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run with coverage
pytest --cov=src tests/
```

### Code Quality

```bash
# Type checking
mypy src/

# Linting
ruff check src/

# Formatting
ruff format src/
```

## Troubleshooting

### Common Issues

1. **Memory Issues**: Reduce batch size or concurrency
2. **Timeout Issues**: Increase Lambda timeout or reduce batch size
3. **S3 Permissions**: Ensure proper IAM permissions
4. **PDF Processing Errors**: Check PDF format and structure

### Debugging

Set `LOG_LEVEL=DEBUG` for detailed logging including:
- S3 operation details
- PDF processing steps
- Image extraction progress
- Retry attempts

## License

MIT License