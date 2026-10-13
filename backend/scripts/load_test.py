from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import httpx
from sqlalchemy.engine import make_url

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402


@dataclass(frozen=True)
class Scenario:
    name: str
    path: str


REGULAR_SCENARIOS = (
    Scenario("products-search", "/api/v1/products/page?offset=0&limit=25&search=0199"),
    Scenario("partners-search", "/api/v1/partners/page?offset=0&limit=25&search=0999"),
    Scenario("documents-search", "/api/v1/documents/page?offset=0&limit=25&search=00999"),
    Scenario(
        "partner-balances",
        "/api/v1/partners/balances?" + "&".join(f"partner_ids={value}" for value in range(1, 26)),
    ),
    Scenario("dashboard", "/api/v1/dashboard/summary?date_from=2025-10-11&recent_limit=6"),
    Scenario("cash-deep-page", "/api/v1/cash/book/page?offset=50000&limit=25"),
)

REPORT_SCENARIOS = (
    Scenario(
        "documents-register",
        "/api/v1/reports/documents-register?date_from=2026-10-01&date_to=2026-10-11",
    ),
    Scenario(
        "cash-book-report",
        "/api/v1/reports/cash-book?date_from=2026-10-01&date_to=2026-10-11",
    ),
    Scenario(
        "partner-debts-report",
        "/api/v1/reports/partner-debts?partner_type=customer&only_with_balance=true",
    ),
    Scenario("stock-balances-report", "/api/v1/reports/stock-balances?warehouse_id=1"),
)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, int(len(ordered) * fraction + 0.999999) - 1))
    return ordered[index]


def require_performance_database() -> None:
    database_name = make_url(get_settings().database_url).database or ""
    if not database_name.endswith("_perf"):
        raise RuntimeError(f"Refusing to load test non-performance database: {database_name!r}")


def seed_auth() -> None:
    from app.db import base  # noqa: F401
    from app.db.session import SessionLocal
    from app.services.auth_seed import seed_auth_defaults

    with SessionLocal() as db:
        seed_auth_defaults(db)


async def run_profile(
    client: httpx.AsyncClient,
    *,
    profile: str,
    scenarios: tuple[Scenario, ...],
    concurrency: int,
    requests: int,
    slo_ms: float,
) -> dict[str, object]:
    for scenario in scenarios:
        response = await client.get(scenario.path)
        response.raise_for_status()

    queue: asyncio.Queue[tuple[int, Scenario]] = asyncio.Queue()
    for index in range(requests):
        queue.put_nowait((index, scenarios[index % len(scenarios)]))

    timings: dict[str, list[float]] = defaultdict(list)
    status_counts: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    failures: list[dict[str, object]] = []

    async def worker() -> None:
        while not queue.empty():
            try:
                _index, scenario = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            started = perf_counter()
            try:
                response = await client.get(scenario.path)
                elapsed_ms = (perf_counter() - started) * 1000
                timings[scenario.name].append(elapsed_ms)
                status_counts[scenario.name][response.status_code] += 1
                if response.status_code >= 400:
                    failures.append(
                        {
                            "scenario": scenario.name,
                            "status": response.status_code,
                            "body": response.text[:200],
                        }
                    )
            except Exception as exc:  # noqa: BLE001 - load-test evidence must retain request failures
                elapsed_ms = (perf_counter() - started) * 1000
                timings[scenario.name].append(elapsed_ms)
                failures.append({"scenario": scenario.name, "error": str(exc)})
            finally:
                queue.task_done()

    started = perf_counter()
    await asyncio.gather(*(worker() for _ in range(concurrency)))
    elapsed_seconds = perf_counter() - started

    scenario_results: dict[str, object] = {}
    all_timings: list[float] = []
    for scenario in scenarios:
        values = timings[scenario.name]
        all_timings.extend(values)
        scenario_results[scenario.name] = {
            "requests": len(values),
            "status_counts": dict(sorted(status_counts[scenario.name].items())),
            "mean_ms": round(statistics.fmean(values), 2) if values else 0.0,
            "p50_ms": round(percentile(values, 0.50), 2),
            "p95_ms": round(percentile(values, 0.95), 2),
            "p99_ms": round(percentile(values, 0.99), 2),
            "max_ms": round(max(values), 2) if values else 0.0,
        }

    return {
        "profile": profile,
        "concurrency": concurrency,
        "requests": requests,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "throughput_rps": round(requests / elapsed_seconds, 2),
        "error_rate_percent": round(len(failures) / requests * 100, 3),
        "p50_ms": round(percentile(all_timings, 0.50), 2),
        "p95_ms": round(percentile(all_timings, 0.95), 2),
        "p99_ms": round(percentile(all_timings, 0.99), 2),
        "slo_ms": slo_ms,
        "slo_pass": not failures and percentile(all_timings, 0.95) <= slo_ms,
        "scenarios": scenario_results,
        "failures": failures[:20],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Concurrent endpoint-level Buy Modern load test")
    parser.add_argument("--regular-concurrency", type=int, default=12)
    parser.add_argument("--regular-requests", type=int, default=240)
    parser.add_argument("--report-concurrency", type=int, default=4)
    parser.add_argument("--report-requests", type=int, default=40)
    args = parser.parse_args()

    require_performance_database()
    email = os.environ.get("LOAD_TEST_EMAIL")
    password = os.environ.get("LOAD_TEST_PASSWORD")
    if not email or not password:
        raise RuntimeError("LOAD_TEST_EMAIL and LOAD_TEST_PASSWORD are required")

    seed_auth()

    from app.main import app

    transport = httpx.ASGITransport(app=app)
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://load-test", timeout=timeout
    ) as client:
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        login.raise_for_status()
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

        regular = await run_profile(
            client,
            profile="regular",
            scenarios=REGULAR_SCENARIOS,
            concurrency=args.regular_concurrency,
            requests=args.regular_requests,
            slo_ms=2000,
        )
        reports = await run_profile(
            client,
            profile="reports",
            scenarios=REPORT_SCENARIOS,
            concurrency=args.report_concurrency,
            requests=args.report_requests,
            slo_ms=5000,
        )

    print(json.dumps({"regular": regular, "reports": reports}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
