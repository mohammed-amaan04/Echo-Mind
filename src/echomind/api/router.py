from fastapi import APIRouter

from echomind.api.routes.health import router as health_router
from echomind.api.routes.response import router as response_router
from echomind.api.routes.retrieval import router as retrieval_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(retrieval_router)
api_router.include_router(response_router)
