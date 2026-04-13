"""
Structured JSON logging — replaces basic logging throughout the app.
Outputs machine-parseable JSON for CloudWatch + OpenSearch ingestion.
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import structlog


def setup_logging(environment: str = "development") -> None:
    """
    Configure structlog for structured JSON output.

    In production: JSON format for log aggregation.
    In development: human-readable console output.
    """
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.StackInfoRenderer(),
    ]

    if environment == "production":
        processors.extend([
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ])
    else:
        processors.extend([
            structlog.dev.ConsoleRenderer(),
        ])

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure the standard logging module
    log_level = logging.DEBUG if environment == "development" else logging.INFO
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(*args: Any, **kwargs: Any) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(*args, **kwargs)
