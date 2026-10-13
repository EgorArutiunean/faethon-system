import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, str] | None = None,
    token: str | None = None,
) -> tuple[int, dict[str, Any]]:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        urljoin(base_url.rstrip("/") + "/", path.lstrip("/")),
        data=data,
        headers=headers,
        method=method,
    )
    with urlopen(request, timeout=15) as response:
        body = json.loads(response.read().decode("utf-8"))
        return response.status, body


def run() -> dict[str, Any]:
    base_url = require_env("SMOKE_BASE_URL")
    email = require_env("SMOKE_EMAIL")
    password = require_env("SMOKE_PASSWORD")

    live_status, live = request_json(base_url, "/health/live")
    ready_status, ready = request_json(base_url, "/health/ready")
    login_status, login = request_json(
        base_url,
        "/api/v1/auth/login",
        method="POST",
        payload={"email": email, "password": password},
    )
    token = login.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("login response did not contain an access token")
    me_status, me = request_json(base_url, "/api/v1/auth/me", token=token)
    if me.get("must_change_password") is True:
        raise RuntimeError("smoke user must complete the mandatory password change")
    dashboard_status, _ = request_json(
        base_url,
        "/api/v1/dashboard/summary",
        token=token,
    )

    expected = {
        "live": live_status,
        "ready": ready_status,
        "login": login_status,
        "me": me_status,
        "dashboard": dashboard_status,
    }
    if any(status != 200 for status in expected.values()):
        raise RuntimeError(f"unexpected smoke status: {expected}")
    if live.get("status") != "alive" or ready.get("status") != "ready":
        raise RuntimeError("health response has an unexpected status")

    return {
        "status": "passed",
        "checks": expected,
        "schema_revision": ready.get("schema_revision"),
        "smoke_user_id": me.get("id"),
    }


if __name__ == "__main__":
    try:
        print(json.dumps(run(), sort_keys=True))
    except (HTTPError, URLError, RuntimeError, TimeoutError, ValueError) as exc:
        print(
            json.dumps({"status": "failed", "error_type": type(exc).__name__}),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
