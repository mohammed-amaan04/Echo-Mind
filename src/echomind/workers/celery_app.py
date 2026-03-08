from celery import Celery

from echomind.core.config import get_settings

settings = get_settings()

celery_app = Celery("echomind", broker=settings.redis_url, backend=settings.redis_url)


@celery_app.task(name="echomind.ping")
def ping() -> str:
    return "pong"
