from fastapi import FastAPI

from echomind.api.router import api_router
from echomind.core.config import get_settings
from echomind.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title=settings.app_name)
app.include_router(api_router)
