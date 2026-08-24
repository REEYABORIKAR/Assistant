"""
OpenTelemetry tracing setup.

Configures OTel with a local Jaeger/OTLP exporter for development.
Production should point to a real OTLP collector.
"""
import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

logger = logging.getLogger(__name__)

# OTLP exporter is optional — if Jaeger isn't running, tracing still works in-process
_OTEL_EXPORTER = None
try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    _OTEL_EXPORTER = OTLPSpanExporter
except ImportError:
    pass


def init_tracing(app=None, service_name: str = "refyne-backend") -> TracerProvider:
    """
    Initialize OpenTelemetry tracing with OTLP exporter.

    Args:
        app: FastAPI app instance (unused — FastAPI auto-instrumentation disabled
             due to version incompatibility; use manual spans instead).
        service_name: Service name for traces (default: refyne-backend).

    Returns:
        Configured TracerProvider.
    """
    resource = Resource.create({SERVICE_NAME: service_name})

    # Sampling: always sample in dev, configurable in prod
    sampler_name = os.environ.get("OTEL_SAMPLER", "always_on")
    if sampler_name == "always_on":
        from opentelemetry.sdk.trace.sampling import ALWAYS_ON
        sampler = ALWAYS_ON
    elif sampler_name == "always_off":
        from opentelemetry.sdk.trace.sampling import ALWAYS_OFF
        sampler = ALWAYS_OFF
    else:
        ratio = float(os.environ.get("OTEL_SAMPLER_RATIO", "1.0"))
        sampler = TraceIdRatioBased(ratio)

    provider = TracerProvider(resource=resource, sampler=sampler)

    # OTLP exporter (sends to Jaeger or any OTLP collector)
    if _OTEL_EXPORTER is not None:
        otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        try:
            exporter = _OTEL_EXPORTER(endpoint=otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except Exception:
            pass

    trace.set_tracer_provider(provider)

    # NOTE: FastAPI auto-instrumentation disabled — opentelemetry-instrumentation-fastapi
    # v0.54b0 is incompatible with the installed Starlette version.
    # Use manual spans via get_tracer() instead.

    return provider


def get_tracer(name: str = "refyne") -> trace.Tracer:
    """Get a tracer instance."""
    return trace.get_tracer(name)
