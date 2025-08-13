"""AWS Lambda entry point for BP-ECG ETL anonymization pipeline.

Simple, clean Lambda function that processes S3 events containing PDF files
and applies anonymization using the streamlined pipeline.
"""

# Import the simplified Lambda handler
from bp_ecg_etl.lambda_main import lambda_handler
from bp_ecg_etl.logging_config import setup_logging

# Initialize logging
setup_logging()

# Export the main handler for Lambda runtime
__all__ = ["lambda_handler"]


def main():
    """Main function for local testing (not used in Lambda)."""
    import structlog
    from bp_ecg_etl.config import INPUT_BUCKET, OUTPUT_BUCKET

    logger = structlog.get_logger(__name__)

    logger.info(
        "BP-ECG ETL Anonymization Pipeline initialized",
        input_bucket=INPUT_BUCKET,
        output_bucket=OUTPUT_BUCKET,
    )
    print("Lambda handler ready for S3 events")


if __name__ == "__main__":
    main()
