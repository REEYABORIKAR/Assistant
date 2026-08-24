import logging
import os
import time
from datetime import UTC, datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, projects, workspaces
from app.core.database import Base, engine
from app.core.logging_config import setup_logging
from app.core.tracing import init_tracing

# import models to ensure they are registered with Base
from app.models import review

load_dotenv()

logger = logging.getLogger(__name__)

# Initialize structured logging
setup_logging()

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Refyne AI Backend")

# Initialize OpenTelemetry tracing
init_tracing(app)

# Configure CORS
origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174,http://localhost:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(workspaces.router)
from app.api import documents

app.include_router(documents.router)
from app.api import retrieval

app.include_router(retrieval.router)
from app.api import document_generation

app.include_router(document_generation.router)
from app.api import supervisor

app.include_router(supervisor.router)
from app.api import supervisor_chat

app.include_router(supervisor_chat.router)
from app.api import review

app.include_router(review.router)
from app.api import audit

app.include_router(audit.router)
from app.api import dashboard, artifacts, requirements_api, validations_api

app.include_router(dashboard.router)
app.include_router(artifacts.router)
app.include_router(requirements_api.router)
app.include_router(validations_api.router)

_start_time = time.monotonic()


@app.get("/health")
def health_check():
    """Liveness: is the process up and responding."""
    return {"status": "ok"}


@app.get("/ready")
def readiness_check(response: Response):
    """Readiness: can this instance actually serve requests (DB reachable)."""
    checks = {}

    # Database
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Redis (optional — fail gracefully if not configured)
    redis_url = os.getenv("CELERY_BROKER_URL")
    if redis_url:
        try:
            import redis as redis_lib
            r = redis_lib.from_url(redis_url, socket_timeout=2)
            r.ping()
            checks["redis"] = "ok"
        except Exception as e:
            checks["redis"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503
    response.status_code = status_code

    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
        "uptime_seconds": round(time.monotonic() - _start_time, 1),
    }


@app.get("/metrics")
def metrics_summary():
    """
    Simple metrics summary endpoint.
    Returns basic counters and histograms as JSON.
    For full Prometheus integration, add prometheus_client and wire it to OTel in Phase E.
    """
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "note": "Basic JSON summary. Full Prometheus/Grafana dashboard is Phase E scope.",
        "tracing": {
            "otlp_endpoint": os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
            "jaeger_ui": "http://localhost:16686",
        },
    }
