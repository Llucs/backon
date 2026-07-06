import backon
from backon._instrumentation import (
    MetricsCollector,
    StructlogMetrics,
    _auto_detect_collector,
)


class TestStructlogMetrics:
    def test_importable(self):
        assert hasattr(backon, "StructlogMetrics")

    def test_fallback_when_not_installed(self):
        m = StructlogMetrics()
        assert m._enabled is False

    def test_noop_methods_dont_raise(self):
        m = StructlogMetrics()
        m.emit_attempt(1, 0.5, "test")
        m.emit_success(2, 1.0, "test")
        m.emit_failure(1, 0.5, "test", "ValueError")
        m.emit_circuit_breaker_open("breaker1")
        m.emit_circuit_breaker_close("breaker1")
        m.emit_hedge_request("test", 3)


class TestAutoDetection:
    def test_auto_detect_fallback(self):
        collector = _auto_detect_collector()
        assert isinstance(collector, (MetricsCollector,))

    def test_set_and_get(self):
        original = backon.get_metrics_collector()
        custom = MetricsCollector()
        backon.set_metrics_collector(custom)
        assert backon.get_metrics_collector() is custom
        backon.set_metrics_collector(original)

    def test_default_noop_does_not_raise(self):
        collector = backon.get_metrics_collector()
        collector.emit_attempt(1, 0.5, "test")
        collector.emit_success(1, 0.5, "test")
        collector.emit_failure(1, 0.5, "test", "ValueError")
