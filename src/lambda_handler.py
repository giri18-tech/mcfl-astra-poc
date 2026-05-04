"""AWS Lambda entry — API Gateway (HTTP API) → ASGI via Mangum."""

import logging

# Logging must be configured before any module that logs at import time.
from config.logging_config import configure as _configure_logging
from config.settings import settings

_configure_logging(settings.LOG_LEVEL)

logger = logging.getLogger(__name__)
logger.info("Lambda cold start", extra={"service": settings.APP_NAME})

from mangum import Mangum  # noqa: E402

from main import app  # noqa: E402

handler = Mangum(app, lifespan="off")
