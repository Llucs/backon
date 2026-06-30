from __future__ import annotations

import logging
from typing import Any

_logger = logging.getLogger("backon")
_logger.addHandler(logging.NullHandler())


class MetricsCollector:
    def emit_attempt(
        self,
        tries: int,
        elapsed: float,
        target_name: str,
        exception_type: str | None = None,
    ) -> None:
        pass

    def emit_success(self, tries: int, elapsed: float, target_name: str) -> None:
        pass

    def emit_failure(
        self, tries: int, elapsed: float, target_name: str, exception_type: str
    ) -> None:
        pass

    def emit_circuit_breaker_open(self, breaker_name: str) -> None:
        pass

    def emit_circuit_breaker_close(self, breaker_name: str) -> None:
        pass

    def emit_hedge_request(self, target_name: str, hedge_count: int) -> None:
        pass


try:
    import prometheus_client
except ImportError:
    prometheus_client = None


class PrometheusMetrics(MetricsCollector):
    def __init__(self) -> None:
        if prometheus_client is None:
            _logger.warning(
                "prometheus_client not installed; PrometheusMetrics will be a no-op"
            )
            self._enabled = False
            return
        self._enabled = True
        self._attempts = prometheus_client.Counter(
            "backon_retry_attempts_total",
            "Total retry attempts",
            labelnames=["target", "exception_type"],
        )
        self._successes = prometheus_client.Counter(
            "backon_retry_success_total",
            "Total retry successes",
            labelnames=["target"],
        )
        self._failures = prometheus_client.Counter(
            "backon_retry_failure_total",
            "Total retry failures",
            labelnames=["target", "exception_type"],
        )
        self._breaker_open = prometheus_client.Counter(
            "backon_circuit_breaker_open_total",
            "Total circuit breaker opens",
            labelnames=["breaker"],
        )
        self._breaker_close = prometheus_client.Counter(
            "backon_circuit_breaker_close_total",
            "Total circuit breaker closes",
            labelnames=["breaker"],
        )
        self._hedge_requests = prometheus_client.Counter(
            "backon_hedge_requests_total",
            "Total hedge requests",
            labelnames=["target"],
        )

    def emit_attempt(
        self,
        tries: int,
        elapsed: float,
        target_name: str,
        exception_type: str | None = None,
    ) -> None:
        if not self._enabled:
            return
        labels: dict[str, Any] = {"target": target_name}
        if exception_type is not None:
            labels["exception_type"] = exception_type
        self._attempts.labels(**labels).inc()

    def emit_success(self, tries: int, elapsed: float, target_name: str) -> None:
        if not self._enabled:
            return
        self._successes.labels(target=target_name).inc()

    def emit_failure(
        self, tries: int, elapsed: float, target_name: str, exception_type: str
    ) -> None:
        if not self._enabled:
            return
        self._failures.labels(target=target_name, exception_type=exception_type).inc()

    def emit_circuit_breaker_open(self, breaker_name: str) -> None:
        if not self._enabled:
            return
        self._breaker_open.labels(breaker=breaker_name).inc()

    def emit_circuit_breaker_close(self, breaker_name: str) -> None:
        if not self._enabled:
            return
        self._breaker_close.labels(breaker=breaker_name).inc()

    def emit_hedge_request(self, target_name: str, hedge_count: int) -> None:
        if not self._enabled:
            return
        self._hedge_requests.labels(target=target_name).inc(hedge_count)


try:
    from opentelemetry import metrics as otel_metrics
except ImportError:
    otel_metrics = None


class OTelMetrics(MetricsCollector):
    def __init__(self, meter_name: str = "backon") -> None:
        if otel_metrics is None:
            _logger.warning(
                "opentelemetry-api not installed; OTelMetrics will be a no-op"
            )
            self._enabled = False
            return
        self._enabled = True
        meter = otel_metrics.get_meter(meter_name)
        self._attempts = meter.create_counter(
            "backon.retry.attempts",
            unit="1",
            description="Total retry attempts",
        )
        self._successes = meter.create_counter(
            "backon.retry.success",
            unit="1",
            description="Total retry successes",
        )
        self._failures = meter.create_counter(
            "backon.retry.failure",
            unit="1",
            description="Total retry failures",
        )
        self._breaker_open = meter.create_counter(
            "backon.circuit_breaker.open",
            unit="1",
            description="Total circuit breaker opens",
        )
        self._breaker_close = meter.create_counter(
            "backon.circuit_breaker.close",
            unit="1",
            description="Total circuit breaker closes",
        )
        self._hedge_requests = meter.create_counter(
            "backon.hedge.requests",
            unit="1",
            description="Total hedge requests",
        )
        self._attempt_duration = meter.create_histogram(
            "backon.retry.attempt_duration",
            unit="s",
            description="Duration of retry attempts",
        )

    def emit_attempt(
        self,
        tries: int,
        elapsed: float,
        target_name: str,
        exception_type: str | None = None,
    ) -> None:
        if not self._enabled:
            return
        attrs: dict[str, Any] = {"target": target_name}
        if exception_type is not None:
            attrs["exception_type"] = exception_type
        self._attempts.add(tries, attributes=attrs)
        self._attempt_duration.record(elapsed, attributes=attrs)

    def emit_success(self, tries: int, elapsed: float, target_name: str) -> None:
        if not self._enabled:
            return
        attrs = {"target": target_name}
        self._successes.add(1, attributes=attrs)

    def emit_failure(
        self, tries: int, elapsed: float, target_name: str, exception_type: str
    ) -> None:
        if not self._enabled:
            return
        attrs = {"target": target_name, "exception_type": exception_type}
        self._failures.add(1, attributes=attrs)

    def emit_circuit_breaker_open(self, breaker_name: str) -> None:
        if not self._enabled:
            return
        attrs = {"breaker": breaker_name}
        self._breaker_open.add(1, attributes=attrs)

    def emit_circuit_breaker_close(self, breaker_name: str) -> None:
        if not self._enabled:
            return
        attrs = {"breaker": breaker_name}
        self._breaker_close.add(1, attributes=attrs)

    def emit_hedge_request(self, target_name: str, hedge_count: int) -> None:
        if not self._enabled:
            return
        attrs = {"target": target_name}
        self._hedge_requests.add(hedge_count, attributes=attrs)


_metrics_collector: MetricsCollector = MetricsCollector()


def set_metrics_collector(collector: MetricsCollector) -> None:
    global _metrics_collector
    _metrics_collector = collector


def get_metrics_collector() -> MetricsCollector:
    return _metrics_collector
