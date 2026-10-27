import logging

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.schemas.common import ErrorResponse

logging.basicConfig(level=logging.INFO)

_ERROR_RESPONSES = {code: {"model": ErrorResponse} for code in (400, 401, 403, 404, 409, 422, 500)}


def create_app() -> FastAPI:
    app = FastAPI(
        title=get_settings().app_name,
        version="1.0.0",
        description=(
            "Track metal supplier offers (aluminium dross, slag, ingots...) and deals "
            "through an auditable status workflow."
        ),
        responses=_ERROR_RESPONSES,
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app


app = create_app()
