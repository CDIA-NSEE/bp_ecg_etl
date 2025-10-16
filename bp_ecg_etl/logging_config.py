"""Optimized logging configuration for CloudWatch with sampling and aggregation."""

import logging
import os
import sys

import structlog

# CloudWatch optimization settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_SAMPLING_RATE = float(os.getenv("LOG_SAMPLING_RATE", "0.1"))  # Log 10% of success operations
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # json or console


class SamplingFilter(logging.Filter):
    """Filter that samples INFO logs to reduce CloudWatch costs.
    
    - Always logs ERROR and WARNING
    - Samples INFO logs based on SAMPLING_RATE
    - Always logs messages with 'summary' or 'completed' keywords
    """
    
    def __init__(self, sampling_rate: float = 0.1):
        super().__init__()
        self.sampling_rate = sampling_rate
        self.counter = 0
        self.sample_every = max(1, int(1.0 / sampling_rate)) if sampling_rate > 0 else 1
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Always log errors and warnings
        if record.levelno >= logging.WARNING:
            return True
        
        # Always log summary/important messages
        msg = str(record.msg).lower()
        if any(keyword in msg for keyword in ['summary', 'completed', 'started', 'finished', 'failed']):
            return True
        
        # Sample INFO logs
        if record.levelno == logging.INFO:
            self.counter += 1
            if self.counter % self.sample_every == 0:
                return True
            return False
        
        return True


def setup_logging():
    """Configure optimized structlog for ECS/CloudWatch environment.
    
    Optimizations:
    - Sampling for INFO logs to reduce CloudWatch ingestion
    - Compact JSON format
    - Efficient timestamp formatting
    - Minimal processors for performance
    """
    # Configure Python's logging to stdout (CloudWatch captures this)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, LOG_LEVEL),
    )
    
    # Add sampling filter to root logger
    root_logger = logging.getLogger()
    root_logger.addFilter(SamplingFilter(sampling_rate=LOG_SAMPLING_RATE))
    
    # Choose processors based on format
    if LOG_FORMAT == "json":
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(sort_keys=False),  # Faster without sorting
        ]
    else:
        # Console format for local testing
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ]
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__):
    """Get a structlog logger."""
    return structlog.get_logger(name)


# Initialize logging
setup_logging()
