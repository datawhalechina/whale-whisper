import logging
import time

from fastapi import FastAPI

from app.core.settings import get_settings
from app.extensions import ext_catalogs, ext_cors, ext_engines, ext_logging

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    start_time = time.perf_counter()
    app = FastAPI(title=settings.app_name)
    initialize_extensions(app)
    end_time = time.perf_counter()
    if settings.debug:
        logger.info("Finished create_app (%s ms)", round((end_time - start_time) * 1000, 2))
    return app


def initialize_extensions(app: FastAPI) -> None:
    extensions = [
        ext_logging,
        ext_cors,
        ext_engines,
        ext_catalogs,
    ]
    for ext in extensions:
        ext.init_app(app)
