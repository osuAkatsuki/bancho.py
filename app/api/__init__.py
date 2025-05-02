# type: ignore
# isort: dont-add-imports

from fastapi import APIRouter

from .rest.v1 import apiv1_router
from .rest.v2 import apiv2_router
from .bancho import bancho_router
from .redirect import redirect_router
from .static import static_router
from .web import web_router

router = APIRouter()

router.include_router(bancho_router)
router.include_router(redirect_router)
router.include_router(static_router)
router.include_router(web_router)

router.include_router(apiv1_router)
router.include_router(apiv2_router)

from . import domains
from . import init_api
from . import middlewares
