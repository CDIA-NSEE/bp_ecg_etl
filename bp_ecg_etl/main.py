"""AWS Lambda entry point for BP-ECG ETL anonymization pipeline.

Simple, clean Lambda function that processes S3 events containing PDF files
and applies anonymization using the streamlined pipeline.
"""

# Import the simplified Lambda handler
from .lambda_main import lambda_handler
from . import config
from .logging_config import setup_logging

# Initialize logging
setup_logging()

# Export the main handler for Lambda runtime
__all__ = ['lambda_handler']

def main():
    """Main function for local testing (not used in Lambda)."""
    import structlog
    logger = structlog.get_logger(__name__)
    
    logger.info(
        "BP-ECG ETL Anonymization Pipeline initialized",
        input_bucket=config.INPUT_BUCKET,
        output_bucket=config.OUTPUT_BUCKET
    )
    print("Lambda handler ready for S3 events")

if __name__ == "__main__":
    main()
