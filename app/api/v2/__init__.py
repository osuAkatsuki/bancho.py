# isort: dont-add-imports

from typing import Any
from typing import TypedDict

import jwt
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status

from app import settings
from app.api.v2.common.oauth import OAuth2Scheme

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


class AuthorizationContext(TypedDict):
    verified_claims: dict[str, Any]


async def authenticate_api_request(
    token: str = Depends(oauth2_scheme),
) -> AuthorizationContext:
    verified_claims: dict[str, Any] | None = None
    try:
        verified_claims = jwt.decode(
            token,
            settings.JWT_PRIVATE_KEY,
            algorithms=["HS256"],
            options={"require": ["exp", "nbf", "iss", "aud", "iat"]},
        )
    except jwt.InvalidTokenError:
        pass

    if verified_claims is None:
        try:
            verified_claims = jwt.decode(
                token,
                settings.ROTATION_JWT_PRIVATE_KEY,
                algorithms=["HS256"],
                options={"require": ["exp", "nbf", "iss", "aud", "iat"]},
            )
        except jwt.InvalidTokenError:
            pass

    if verified_claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthorizationContext(
        verified_claims=verified_claims,
    )


from . import clans
from . import maps
from . import oauth
from . import players
from . import scores

apiv2_router = APIRouter(tags=["API v2"], prefix="/v2")

apiv2_router.include_router(clans.router)
apiv2_router.include_router(maps.router)
apiv2_router.include_router(players.router)
apiv2_router.include_router(scores.router)
apiv2_router.include_router(oauth.router)
