from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from backon._instrumentation import (
    MetricsCollector,
    _metrics_collector,
    get_metrics_collector,
    set_metrics_collector,
)


class TestMetricsCollectorNoop:
    def setup_method(self) -> None:
        self.collector = MetricsCollector()

    def test_emit_attempt(self) -> None:
        self.collector.emit_attempt(1, 0.5, "func")
        self.collector.emit_attempt(2, 1.0, "func", "ValueError")

    def test_emit_success(self) -> None:
        self.collector.emit_success(3, 2.0, "func")

    def test_emit_failure(self) -> None:
        self.collector.emit_failure(3, 2.0, "func", "ValueError")

    def test_emit_circuit_breaker_open(self) -> None:
        self.collector.emit_circuit_breaker_open("breaker1")

    def test_emit_circuit_breaker_close(self) -> None:
        self.collector.emit_circuit_breaker_close("breaker1")

    def test_emit_hedge_request(self) -> None:
        self.collector.emit_hedge_request("func", 2)

    def test_all_methods_accept_params(self) -> None:
        self.collector.emit_attempt(0, 0.0, "", None)
        self.collector.emit_attempt(0, 0.0, "", "Exc")
        self.collector.emit_success(0, 0.0, "")
        self.collector.emit_failure(0, 0.0, "", "Exc")
        self.collector.emit_circuit_breaker_open("")
        self.collector.emit_circuit_breaker_close("")
        self.collector.emit_hedge_request("", 0)


class TestPrometheusMetrics:
    def test_noop_when_not_installed(self) -> None:
        with patch.dict("sys.modules", {"prometheus_client": None}):
            with patch("backon._instrumentation.prometheus_client", None):
                with patch("backon._instrumentation._logger.warning") as mock_warn:
                    from backon._instrumentation import PrometheusMetrics

                    pm = PrometheusMetrics()
                    assert pm._enabled is False
                    mock_warn.assert_called_once()
                    pm.emit_attempt(1, 0.5, "func")
                    pm.emit_success(1, 0.5, "func")
                    pm.emit_failure(1, 0.5, "func", "Exc")
                    pm.emit_circuit_breaker_open("b")
                    pm.emit_circuit_breaker_close("b")
                    pm.emit_hedge_request("func", 2)

    def test_with_mock_prometheus(self) -> None:
        mock_counter = MagicMock()
        mock_counter_class = MagicMock(return_value=mock_counter)

        mock_prom = MagicMock()
        mock_prom.Counter = mock_counter_class

        with patch.dict("sys.modules", {"prometheus_client": mock_prom}):
            with patch("backon._instrumentation.prometheus_client", mock_prom):
                from backon._instrumentation import PrometheusMetrics

                pm = PrometheusMetrics()
                assert pm._enabled is True
                assert mock_counter_class.call_count == 6

                pm.emit_attempt(1, 0.5, "func")
                mock_counter.labels.assert_called_with(target="func")
                mock_counter.labels.return_value.inc.assert_called_once()

                pm.emit_success(2, 1.0, "func")
                assert mock_counter.labels.call_count >= 2

    def test_attempt_with_exception(self) -> None:
        mock_counter = MagicMock()
        mock_counter_class = MagicMock(return_value=mock_counter)
        mock_prom = MagicMock()
        mock_prom.Counter = mock_counter_class

        with patch.dict("sys.modules", {"prometheus_client": mock_prom}):
            with patch("backon._instrumentation.prometheus_client", mock_prom):
                from backon._instrumentation import PrometheusMetrics

                pm = PrometheusMetrics()
                pm.emit_attempt(1, 0.5, "func", "ValueError")
                mock_counter.labels.assert_called_with(
                    target="func", exception_type="ValueError"
                )

    def test_hedge_with_increment(self) -> None:
        mock_counter = MagicMock()
        mock_counter_class = MagicMock(return_value=mock_counter)
        mock_prom = MagicMock()
        mock_prom.Counter = mock_counter_class

        with patch.dict("sys.modules", {"prometheus_client": mock_prom}):
            with patch("backon._instrumentation.prometheus_client", mock_prom):
                from backon._instrumentation import PrometheusMetrics

                pm = PrometheusMetrics()
                pm.emit_hedge_request("func", 3)
                mock_counter.labels.assert_called_with(target="func")
                mock_counter.labels.return_value.inc.assert_called_with(3)


class TestOTelMetrics:
    def test_noop_when_not_installed(self) -> None:
        with patch.dict("sys.modules", {"opentelemetry": None}):
            with patch("backon._instrumentation.otel_metrics", None):
                with patch("backon._instrumentation._logger.warning") as mock_warn:
                    from backon._instrumentation import OTelMetrics

                    ot = OTelMetrics()
                    assert ot._enabled is False
                    mock_warn.assert_called_once()
                    ot.emit_attempt(1, 0.5, "func")
                    ot.emit_success(1, 0.5, "func")
                    ot.emit_failure(1, 0.5, "func", "Exc")
                    ot.emit_circuit_breaker_open("b")
                    ot.emit_circuit_breaker_close("b")
                    ot.emit_hedge_request("func", 2)

    def test_with_mock_otel(self) -> None:
        mock_counter = MagicMock()
        mock_histogram = MagicMock()
        mock_meter = MagicMock()
        mock_meter.create_counter = MagicMock(return_value=mock_counter)
        mock_meter.create_histogram = MagicMock(return_value=mock_histogram)

        mock_metrics = MagicMock()
        mock_metrics.get_meter = MagicMock(return_value=mock_meter)

        with patch.dict(
            "sys.modules",
            {"opentelemetry": MagicMock(), "opentelemetry.metrics": mock_metrics},
        ):
            with patch("backon._instrumentation.otel_metrics", mock_metrics):
                from backon._instrumentation import OTelMetrics

                ot = OTelMetrics()
                assert ot._enabled is True
                mock_metrics.get_meter.assert_called_once_with("backon")
                assert mock_meter.create_counter.call_count == 6
                assert mock_meter.create_histogram.call_count == 1

                ot.emit_attempt(1, 0.5, "func")
                mock_counter.add.assert_called_with(1, attributes={"target": "func"})
                mock_histogram.record.assert_called_with(
                    0.5, attributes={"target": "func"}
                )

                ot.emit_success(2, 1.0, "func")
                mock_counter.add.assert_called_with(1, attributes={"target": "func"})

    def test_custom_meter_name(self) -> None:
        mock_meter = MagicMock()
        mock_meter.create_counter = MagicMock(return_value=MagicMock())
        mock_meter.create_histogram = MagicMock(return_value=MagicMock())
        mock_metrics = MagicMock()
        mock_metrics.get_meter = MagicMock(return_value=mock_meter)

        with patch.dict(
            "sys.modules",
            {"opentelemetry": MagicMock(), "opentelemetry.metrics": mock_metrics},
        ):
            with patch("backon._instrumentation.otel_metrics", mock_metrics):
                from backon._instrumentation import OTelMetrics

                OTelMetrics("custom_meter")
                mock_metrics.get_meter.assert_called_with("custom_meter")


class TestGlobalCollector:
    def test_default_is_metrics_collector(self) -> None:
        assert isinstance(_metrics_collector, MetricsCollector)
        assert isinstance(get_metrics_collector(), MetricsCollector)

    def test_set_and_get(self) -> None:
        original = get_metrics_collector()
        custom = MetricsCollector()
        set_metrics_collector(custom)
        try:
            assert get_metrics_collector() is custom
        finally:
            set_metrics_collector(original)

    def test_set_back_to_default(self) -> None:
        original = MetricsCollector()
        set_metrics_collector(original)
        assert get_metrics_collector() is original

    def test_global_collector_calls_work(self) -> None:
        collector = get_metrics_collector()
        collector.emit_attempt(1, 0.1, "test")
        collector.emit_success(1, 0.1, "test")
        collector.emit_failure(1, 0.1, "test", "Exc")
        collector.emit_circuit_breaker_open("b")
        collector.emit_circuit_breaker_close("b")
        collector.emit_hedge_request("test", 1)


class TestParameterTypes:
    def test_passes_correct_types_to_collector(self) -> None:
        calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

        class TrackingCollector(MetricsCollector):
            def emit_attempt(
                self,
                tries: int,
                elapsed: float,
                target_name: str,
                exception_type: str | None = None,
            ) -> None:
                calls.append(("emit_attempt", (tries, elapsed, target_name), {}))

            def emit_success(
                self, tries: int, elapsed: float, target_name: str
            ) -> None:
                calls.append(("emit_success", (tries, elapsed, target_name), {}))

            def emit_failure(
                self,
                tries: int,
                elapsed: float,
                target_name: str,
                exception_type: str,
            ) -> None:
                calls.append(
                    (
                        "emit_failure",
                        (tries, elapsed, target_name, exception_type),
                        {},
                    )
                )

            def emit_circuit_breaker_open(self, breaker_name: str) -> None:
                calls.append(
                    (
                        "emit_circuit_breaker_open",
                        (breaker_name,),
                        {},
                    )
                )

            def emit_circuit_breaker_close(self, breaker_name: str) -> None:
                calls.append(
                    (
                        "emit_circuit_breaker_close",
                        (breaker_name,),
                        {},
                    )
                )

            def emit_hedge_request(self, target_name: str, hedge_count: int) -> None:
                calls.append(
                    (
                        "emit_hedge_request",
                        (target_name, hedge_count),
                        {},
                    )
                )

        c = TrackingCollector()
        c.emit_attempt(1, 0.5, "f")
        c.emit_attempt(2, 1.0, "f", "Exc")
        c.emit_success(3, 1.5, "f")
        c.emit_failure(4, 2.0, "f", "Exc")
        c.emit_circuit_breaker_open("b1")
        c.emit_circuit_breaker_close("b2")
        c.emit_hedge_request("f", 3)

        assert len(calls) == 7
        assert calls[0] == ("emit_attempt", (1, 0.5, "f"), {})
        assert calls[1] == (
            "emit_attempt",
            (2, 1.0, "f"),
            {},
        )
        assert calls[2] == ("emit_success", (3, 1.5, "f"), {})
        assert calls[3] == (
            "emit_failure",
            (4, 2.0, "f", "Exc"),
            {},
        )
        assert calls[4] == (
            "emit_circuit_breaker_open",
            ("b1",),
            {},
        )
        assert calls[5] == (
            "emit_circuit_breaker_close",
            ("b2",),
            {},
        )
        assert calls[6] == (
            "emit_hedge_request",
            ("f", 3),
            {},
        )
