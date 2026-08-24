"""
Application Metrics.

Counters and histograms for request tracking, LLM latency, retrieval latency, and validation scores.
Uses OpenTelemetry metrics API with a Prometheus exporter for local dev.
"""
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader

_meter = None


def init_metrics(export_interval_ms: int = 30000) -> MeterProvider:
    """
    Initialize OpenTelemetry metrics.

    Args:
        export_interval_ms: How often to export metrics (default: 30s).

    Returns:
        Configured MeterProvider.
    """
    global _meter

    reader = PeriodicExportingMetricReader(
        exporter=ConsoleMetricExporter(),
        export_interval_millis=export_interval_ms,
    )
    provider = MeterProvider(metric_readers=[reader])
    metrics.set_meter_provider(provider)
    _meter = metrics.get_meter("refyne-backend")
    return provider


def get_meter():
    """Get the application meter, initializing if needed."""
    global _meter
    if _meter is None:
        init_metrics()
    return _meter


# ── Counters ──────────────────────────────────────────────────────────────────

def incr_requests(route: str, status: str = "success"):
    """Increment request counter."""
    meter = get_meter()
    counter = meter.create_counter(
        name="refyne.requests.total",
        description="Total number of API requests",
        unit="1",
    )
    counter.add(1, {"route": route, "status": status})


def incr_retrieval(project_id: str = ""):
    """Increment retrieval counter."""
    meter = get_meter()
    counter = meter.create_counter(
        name="refyne.retrieval.total",
        description="Total number of retrieval operations",
        unit="1",
    )
    counter.add(1, {"project_id": project_id})


def incr_generation(project_id: str = "", configured: bool = True):
    """Increment generation counter."""
    meter = get_meter()
    counter = meter.create_counter(
        name="refyne.generation.total",
        description="Total number of LLM generation calls",
        unit="1",
    )
    counter.add(1, {"project_id": project_id, "configured": str(configured).lower()})


def incr_validation(project_id: str = "", status: str = "pass"):
    """Increment validation counter."""
    meter = get_meter()
    counter = meter.create_counter(
        name="refyne.validation.total",
        description="Total number of validation runs",
        unit="1",
    )
    counter.add(1, {"project_id": project_id, "status": status})


# ── Histograms ────────────────────────────────────────────────────────────────

def observe_retrieval_latency(ms: float, project_id: str = ""):
    """Record retrieval latency."""
    meter = get_meter()
    histogram = meter.create_histogram(
        name="refyne.retrieval.latency_ms",
        description="Retrieval pipeline latency in milliseconds",
        unit="ms",
    )
    histogram.record(ms, {"project_id": project_id})


def observe_generation_latency(ms: float, project_id: str = ""):
    """Record LLM generation latency."""
    meter = get_meter()
    histogram = meter.create_histogram(
        name="refyne.generation.latency_ms",
        description="LLM generation latency in milliseconds",
        unit="ms",
    )
    histogram.record(ms, {"project_id": project_id})


def observe_validation_score(score: float, project_id: str = ""):
    """Record validation score."""
    meter = get_meter()
    histogram = meter.create_histogram(
        name="refyne.validation.score",
        description="Validation score distribution",
        unit="1",
    )
    histogram.record(score, {"project_id": project_id})
