from __future__ import annotations

import base64

from fastapi import Request
from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.openapi.models import OAuthFlowAuthorizationCode
from fastapi.openapi.models import OAuthFlowClientCredentials
from fastapi.openapi.models import OAuthFlows
from fastapi.security import OAuth2
from fastapi.security.utils import get_authorization_scheme_param


class OAuth2Scheme(OAuth2):
    def __init__(
        self,
        authorizationUrl: str,
        tokenUrl: str,
        refreshUrl: str | None = None,
        scheme_name: str | None = None,
        scopes: dict[str, str] | None = None,
        description: str | None = None,
        auto_error: bool = True,
    ):
        if not scopes:
            scopes = {}
        flows = OAuthFlows(
            authorizationCode=OAuthFlowAuthorizationCode(
                authorizationUrl=authorizationUrl,
                tokenUrl=tokenUrl,
                scopes=scopes,
                refreshUrl=refreshUrl,
            ),
            clientCredentials=OAuthFlowClientCredentials(
                tokenUrl=tokenUrl,
                scopes=scopes,
                refreshUrl=refreshUrl,
            ),
        )
        super().__init__(
            flows=flows,
            scheme_name=scheme_name,
            description=description,
            auto_error=auto_error,
        )

    async def __call__(self, request: Request) -> str | None:
        authorization = request.headers.get("Authorization")
        scheme, param = get_authorization_scheme_param(authorization)
        if not authorization or scheme.lower() != "bearer":
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            else:
                return None
        return param


# https://developer.zendesk.com/api-reference/sales-crm/authentication/requests/#client-authentication
def get_credentials_from_basic_auth(
    request: Request,
) -> dict[str, str | int] | None:
    authorization = request.headers.get("Authorization")
    scheme, param = get_authorization_scheme_param(authorization)
    if not authorization or scheme.lower() != "basic":
        return None

    data = base64.b64decode(param).decode("utf-8")
    if ":" not in data:
        return None

    data = data.split(":")
    if len(data) != 2:
        return None
    if not data[0].isdecimal():
        return None

    return {
        "client_id": int(data[0]),
        "client_secret": data[1],
    }
