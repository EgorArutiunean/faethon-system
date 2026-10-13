from fastapi import APIRouter, Response

from app.core.metrics import request_metrics
from app.db.session import engine

router = APIRouter(tags=["metrics"])


@router.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> Response:
    return Response(
        request_metrics.render(engine.pool),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
