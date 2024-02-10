# type: ignore
# isort: dont-add-imports

from fastapi import APIRouter

from .api import router


apiv1_router = APIRouter(tags=["API v1"], prefix="/v1")

apiv1_router.include_router(router)
