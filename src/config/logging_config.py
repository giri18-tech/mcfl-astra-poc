"""
Structured JSON logging for CloudWatch Logs.

Each log line is a JSON object — CloudWatch Insights can query fields directly:
  fields @timestamp, level, logger, message | filter level = "ERROR"
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Lambda injects aws_request_id into the root logger via addHandler;
        # include it when present so logs are linkable to a specific invocation.
        if aws_request_id := getattr(record, "aws_request_id", None):
            payload["aws_request_id"] = aws_request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure(level: str = "INFO") -> None:
    """Install JSON logging on the root logger.  Call once at cold start."""
    root = logging.getLogger()
    # Remove any handlers the Lambda runtime pre-installed.
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    # Suppress chatty third-party loggers.
    for noisy in ("uvicorn.access", "mangum", "botocore", "boto3", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
