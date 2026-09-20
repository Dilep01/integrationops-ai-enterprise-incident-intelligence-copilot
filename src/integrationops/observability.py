from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock
from time import perf_counter

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

_lock = Lock()
_counts: Counter[str] = Counter()
_latency_ms_total = 0.0
_configured = False


def configure_telemetry(service_name: str = "integrationops-api") -> None:
    global _configured
    if _configured:
        return
    resource = Resource.create({"service.name": service_name})
    if not isinstance(trace.get_tracer_provider(), TracerProvider):
        trace.set_tracer_provider(TracerProvider(resource=resource))
    if not isinstance(metrics.get_meter_provider(), MeterProvider):
        metrics.set_meter_provider(MeterProvider(resource=resource))
    _configured = True


@contextmanager
def investigation_span(attributes: dict[str, str]) -> Iterator[None]:
    global _latency_ms_total
    tracer = trace.get_tracer("integrationops.investigation")
    started = perf_counter()
    with tracer.start_as_current_span("investigation.run", attributes=attributes) as span:
        try:
            yield
        except Exception as exc:
            span.record_exception(exc)
            with _lock:
                _counts["investigations_failed"] += 1
            raise
        else:
            with _lock:
                _counts["investigations_completed"] += 1
        finally:
            elapsed = (perf_counter() - started) * 1000
            span.set_attribute("integrationops.duration_ms", elapsed)
            with _lock:
                _counts["investigations_total"] += 1
                _latency_ms_total += elapsed


def record_security_rejection() -> None:
    with _lock:
        _counts["security_rejections"] += 1


def metrics_snapshot() -> dict[str, float | int]:
    with _lock:
        total = _counts["investigations_total"]
        return {
            **dict(_counts),
            "investigations_total": total,
            "average_investigation_latency_ms": round(
                _latency_ms_total / total if total else 0.0, 3
            ),
        }
