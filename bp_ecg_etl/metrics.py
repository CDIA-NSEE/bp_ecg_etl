"""CloudWatch metrics integration for BP-ECG ETL."""

import time
from contextlib import contextmanager
from typing import Iterator

import boto3
import structlog

logger = structlog.get_logger(__name__)

# Initialize CloudWatch client
try:
    cloudwatch = boto3.client('cloudwatch')
except Exception as e:
    logger.warning("Failed to initialize CloudWatch client", error=str(e))
    cloudwatch = None


@contextmanager
def track_duration(metric_name: str, namespace: str = 'BP-ECG-ETL') -> Iterator[None]:
    """Track operation duration and send to CloudWatch.
    
    Args:
        metric_name: Name of the metric
        namespace: CloudWatch namespace
        
    Example:
        with track_duration('PDFProcessing'):
            process_pdf(content)
    """
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        if cloudwatch:
            try:
                cloudwatch.put_metric_data(
                    Namespace=namespace,
                    MetricData=[{
                        'MetricName': metric_name,
                        'Value': duration,
                        'Unit': 'Seconds'
                    }]
                )
            except Exception as e:
                logger.warning("Failed to send metric", metric=metric_name, error=str(e))


def track_pdf_processed(
    success: bool, 
    size_bytes: int, 
    pages: int,
    namespace: str = 'BP-ECG-ETL'
) -> None:
    """Track PDF processing metrics.
    
    Args:
        success: Whether processing succeeded
        size_bytes: Size of PDF in bytes
        pages: Number of pages
        namespace: CloudWatch namespace
    """
    if not cloudwatch:
        return
    
    try:
        cloudwatch.put_metric_data(
            Namespace=namespace,
            MetricData=[
                {
                    'MetricName': 'PDFsProcessed',
                    'Value': 1,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'Success' if success else 'Failure',
                    'Value': 1,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'PDFSize',
                    'Value': size_bytes,
                    'Unit': 'Bytes'
                },
                {
                    'MetricName': 'PageCount',
                    'Value': pages,
                    'Unit': 'Count'
                }
            ]
        )
    except Exception as e:
        logger.warning("Failed to send metrics", error=str(e))


def track_batch_stats(
    total: int,
    successful: int,
    failed: int,
    duration_sec: float,
    namespace: str = 'BP-ECG-ETL'
) -> None:
    """Track batch processing statistics.
    
    Args:
        total: Total PDFs processed
        successful: Number of successful processes
        failed: Number of failures
        duration_sec: Total duration in seconds
        namespace: CloudWatch namespace
    """
    if not cloudwatch:
        return
    
    try:
        cloudwatch.put_metric_data(
            Namespace=namespace,
            MetricData=[
                {
                    'MetricName': 'BatchTotal',
                    'Value': total,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'BatchSuccessful',
                    'Value': successful,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'BatchFailed',
                    'Value': failed,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'BatchDuration',
                    'Value': duration_sec,
                    'Unit': 'Seconds'
                },
                {
                    'MetricName': 'BatchSuccessRate',
                    'Value': (successful / total * 100) if total > 0 else 0,
                    'Unit': 'Percent'
                }
            ]
        )
    except Exception as e:
        logger.warning("Failed to send batch metrics", error=str(e))
