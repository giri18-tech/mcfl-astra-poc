"""AWS Lambda entry — API Gateway (HTTP API) → ASGI via Mangum."""

from mangum import Mangum

from main import app

handler = Mangum(app, lifespan="off")
