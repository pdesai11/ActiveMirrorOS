"""
Health Check & Metrics for ActiveMirrorOS

Provides health check endpoints and Prometheus-compatible metrics.

Usage:
    from activemirror.health import HealthChecker, MetricsCollector

    health = HealthChecker()
    status = health.check()

    metrics = MetricsCollector()
    metrics.record_operation("vault_store", duration_ms=12.5, success=True)

Author: AMOS Dev Twin
"""

from typing import Dict, Any, List
from datetime import datetime
import time
from collections import defaultdict
import threading


class HealthChecker:
    """System health checker."""

    def __init__(self):
        self.checks = []

    def add_check(self, name: str, check_fn: callable):
        """Add a health check function."""
        self.checks.append((name, check_fn))

    def check(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "checks": {},
        }

        for name, check_fn in self.checks:
            try:
                check_result = check_fn()
                results["checks"][name] = {
                    "status": "pass" if check_result else "fail",
                    "details": check_result if isinstance(check_result, dict) else {},
                }

                if not check_result:
                    results["status"] = "unhealthy"

            except Exception as e:
                results["checks"][name] = {
                    "status": "fail",
                    "error": str(e),
                }
                results["status"] = "unhealthy"

        return results

    def check_storage_writable(self, storage) -> bool:
        """Check if storage is writable."""
        try:
            # Try to save a test session
            from activemirror.core.session import Session
            test_session = Session(id="health-check", title="Health Check")
            storage.save_session(test_session)
            storage.delete_session("health-check")
            return True
        except:
            return False

    def check_vault_accessible(self, vault) -> bool:
        """Check if vault is accessible."""
        try:
            # Try to store and retrieve a test value
            vault.store("health-check", "test")
            value = vault.retrieve("health-check")
            vault.delete("health-check")
            return value == "test"
        except:
            return False


class MetricsCollector:
    """Collects and exposes Prometheus-compatible metrics."""

    def __init__(self):
        self.operation_counts = defaultdict(int)
        self.operation_failures = defaultdict(int)
        self.operation_durations = defaultdict(list)
        self.lock = threading.Lock()

    def record_operation(self, operation: str, duration_ms: float = None, success: bool = True):
        """Record an operation metric."""
        with self.lock:
            self.operation_counts[operation] += 1

            if not success:
                self.operation_failures[operation] += 1

            if duration_ms is not None:
                self.operation_durations[operation].append(duration_ms)

                # Keep only last 1000 measurements
                if len(self.operation_durations[operation]) > 1000:
                    self.operation_durations[operation] = self.operation_durations[operation][-1000:]

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        with self.lock:
            metrics = {
                "operation_counts": dict(self.operation_counts),
                "operation_failures": dict(self.operation_failures),
                "operation_durations": {},
            }

            for operation, durations in self.operation_durations.items():
                if durations:
                    metrics["operation_durations"][operation] = {
                        "count": len(durations),
                        "avg_ms": sum(durations) / len(durations),
                        "min_ms": min(durations),
                        "max_ms": max(durations),
                        "p50_ms": self._percentile(durations, 0.5),
                        "p95_ms": self._percentile(durations, 0.95),
                        "p99_ms": self._percentile(durations, 0.99),
                    }

            return metrics

    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile."""
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        metrics = self.get_metrics()

        # Operation counts
        lines.append("# HELP activemirror_operations_total Total number of operations")
        lines.append("# TYPE activemirror_operations_total counter")
        for operation, count in metrics["operation_counts"].items():
            lines.append(f'activemirror_operations_total{{operation="{operation}"}} {count}')

        # Failure counts
        lines.append("\n# HELP activemirror_operation_failures_total Total number of failed operations")
        lines.append("# TYPE activemirror_operation_failures_total counter")
        for operation, count in metrics["operation_failures"].items():
            lines.append(f'activemirror_operation_failures_total{{operation="{operation}"}} {count}')

        # Duration metrics
        lines.append("\n# HELP activemirror_operation_duration_ms Operation duration in milliseconds")
        lines.append("# TYPE activemirror_operation_duration_ms summary")
        for operation, stats in metrics["operation_durations"].items():
            lines.append(f'activemirror_operation_duration_ms{{operation="{operation}",quantile="0.5"}} {stats["p50_ms"]:.2f}')
            lines.append(f'activemirror_operation_duration_ms{{operation="{operation}",quantile="0.95"}} {stats["p95_ms"]:.2f}')
            lines.append(f'activemirror_operation_duration_ms{{operation="{operation}",quantile="0.99"}} {stats["p99_ms"]:.2f}')
            lines.append(f'activemirror_operation_duration_ms_count{{operation="{operation}"}} {stats["count"]}')
            lines.append(f'activemirror_operation_duration_ms_sum{{operation="{operation}"}} {sum(self.operation_durations[operation]):.2f}')

        return "\n".join(lines)


# Global metrics collector
_global_metrics = MetricsCollector()


def get_global_metrics() -> MetricsCollector:
    """Get global metrics collector."""
    return _global_metrics
