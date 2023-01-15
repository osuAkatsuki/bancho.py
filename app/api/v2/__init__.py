# isort: dont-add-imports

from typing import Any

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status

from app.api.v2.common.oauth import OAuth2Scheme
from app.repositories import access_tokens as access_tokens_repo


oauth2_scheme = OAuth2Scheme(
    authorizationUrl="/v2/oauth/authorize",
    tokenUrl="/v2/oauth/token",
    refreshUrl="/v2/oauth/refresh",
    scheme_name="OAuth2 for third-party clients.",
    scopes={
        "public": "Access endpoints with public data.",
        "identify": "Access endpoints with user's data.",
        "admin": "Access admin endpoints.",
    },
)


async def get_current_client(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    """Look up the token in the Redis-based token store"""
    access_token = await access_tokens_repo.fetch_one(token)
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return access_token


from . import clans
from . import maps
from . import players
from . import scores
from . import oauth

apiv2_router = APIRouter(tags=["API v2"], prefix="/v2")

apiv2_router.include_router(clans.router)
apiv2_router.include_router(maps.router)
apiv2_router.include_router(players.router)
apiv2_router.include_router(scores.router)
apiv2_router.include_router(oauth.router)
