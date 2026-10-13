import json
from io import BytesIO
from typing import Any

from scripts import release_smoke


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.status = 200
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return BytesIO(self._body).read()

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_release_smoke_covers_health_login_identity_and_dashboard(monkeypatch) -> None:
    monkeypatch.setenv("SMOKE_BASE_URL", "https://staging.example.test")
    monkeypatch.setenv("SMOKE_EMAIL", "smoke@example.test")
    monkeypatch.setenv("SMOKE_PASSWORD", "not-logged-secret")
    responses = iter(
        [
            FakeResponse({"status": "alive"}),
            FakeResponse({"status": "ready", "schema_revision": "0018"}),
            FakeResponse({"access_token": "private-token"}),
            FakeResponse({"id": 7, "must_change_password": False}),
            FakeResponse({"totals": {}}),
        ]
    )
    requested_paths: list[str] = []

    def fake_urlopen(request, timeout: int):
        del timeout
        requested_paths.append(request.full_url)
        return next(responses)

    monkeypatch.setattr(release_smoke, "urlopen", fake_urlopen)

    result = release_smoke.run()

    assert result == {
        "status": "passed",
        "checks": {"live": 200, "ready": 200, "login": 200, "me": 200, "dashboard": 200},
        "schema_revision": "0018",
        "smoke_user_id": 7,
    }
    assert requested_paths == [
        "https://staging.example.test/health/live",
        "https://staging.example.test/health/ready",
        "https://staging.example.test/api/v1/auth/login",
        "https://staging.example.test/api/v1/auth/me",
        "https://staging.example.test/api/v1/dashboard/summary",
    ]
