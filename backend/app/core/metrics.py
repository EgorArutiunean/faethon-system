from collections import Counter, defaultdict
from threading import Lock
from typing import Any

LATENCY_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)


class RequestMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._active = 0
        self._requests: Counter[tuple[str, str, int]] = Counter()
        self._duration_count: Counter[tuple[str, str]] = Counter()
        self._duration_sum: defaultdict[tuple[str, str], float] = defaultdict(float)
        self._duration_buckets: Counter[tuple[str, str, float]] = Counter()

    def started(self) -> None:
        with self._lock:
            self._active += 1

    def finished(self, method: str, route: str, status_code: int, duration: float) -> None:
        with self._lock:
            self._active -= 1
            self._requests[(method, route, status_code)] += 1
            self._duration_count[(method, route)] += 1
            self._duration_sum[(method, route)] += duration
            for bucket in LATENCY_BUCKETS:
                if duration <= bucket:
                    self._duration_buckets[(method, route, bucket)] += 1

    def render(self, pool: Any) -> str:
        with self._lock:
            lines = [
                "# HELP buy_modern_http_requests_active Current in-flight HTTP requests.",
                "# TYPE buy_modern_http_requests_active gauge",
                f"buy_modern_http_requests_active {self._active}",
                "# HELP buy_modern_http_requests_total Completed HTTP requests.",
                "# TYPE buy_modern_http_requests_total counter",
            ]
            for (method, route, status), value in sorted(self._requests.items()):
                labels = _labels(method=method, route=route, status=str(status))
                lines.append(f"buy_modern_http_requests_total{{{labels}}} {value}")

            lines.extend(
                (
                    "# HELP buy_modern_http_request_duration_seconds HTTP request latency.",
                    "# TYPE buy_modern_http_request_duration_seconds histogram",
                )
            )
            for method, route in sorted(self._duration_count):
                labels = _labels(method=method, route=route)
                for bucket in LATENCY_BUCKETS:
                    count = self._duration_buckets[(method, route, bucket)]
                    lines.append(
                        "buy_modern_http_request_duration_seconds_bucket"
                        f'{{{labels},le="{bucket:g}"}} {count}'
                    )
                count = self._duration_count[(method, route)]
                lines.append(
                    f'buy_modern_http_request_duration_seconds_bucket{{{labels},le="+Inf"}} {count}'
                )
                lines.append(f"buy_modern_http_request_duration_seconds_count{{{labels}}} {count}")
                total = self._duration_sum[(method, route)]
                lines.append(
                    f"buy_modern_http_request_duration_seconds_sum{{{labels}}} {total:.6f}"
                )

        lines.extend(_pool_metrics(pool))
        return "\n".join(lines) + "\n"


def _labels(**values: str) -> str:
    return ",".join(f'{name}="{_escape(value)}"' for name, value in values.items())


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _pool_value(pool: Any, method: str) -> int:
    value = getattr(pool, method, None)
    return int(value()) if callable(value) else 0


def _pool_metrics(pool: Any) -> list[str]:
    values = {
        "size": _pool_value(pool, "size"),
        "checked_out": _pool_value(pool, "checkedout"),
        "checked_in": _pool_value(pool, "checkedin"),
        "overflow": max(0, _pool_value(pool, "overflow")),
    }
    lines = [
        "# HELP buy_modern_db_pool_connections SQLAlchemy connection pool state.",
        "# TYPE buy_modern_db_pool_connections gauge",
    ]
    lines.extend(
        f'buy_modern_db_pool_connections{{state="{state}"}} {value}'
        for state, value in values.items()
    )
    return lines


request_metrics = RequestMetrics()
