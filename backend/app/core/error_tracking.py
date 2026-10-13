from typing import Any
from urllib.parse import urlsplit, urlunsplit

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.types import Event

from app.core.config import Settings


def _strip_url_query(value: object) -> object:
    if not isinstance(value, str):
        return value
    parsed = urlsplit(value)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def scrub_sensitive_event(event: Event, hint: dict[str, Any]) -> Event:
    del hint
    event.pop("user", None)
    request = event.get("request")
    if isinstance(request, dict):
        request["url"] = _strip_url_query(request.get("url"))
        for field in ("cookies", "data", "env", "headers", "query_string"):
            request.pop(field, None)
    return event


def configure_error_tracking(settings: Settings) -> None:
    if not settings.sentry_dsn:
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment or settings.app_env,
        release=settings.release_version,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        before_send=scrub_sensitive_event,
        before_send_transaction=scrub_sensitive_event,
        integrations=[FastApiIntegration(transaction_style="endpoint")],
    )
