"""bancho.py's v2 apis for account management"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from fastapi.requests import Request

from app.api import dependencies as api_dependencies
from app.api.v2.common import responses
from app.api.v2.common.responses import Failure
from app.api.v2.common.responses import Success
from app.api.v2.models.accounts import RegistrationRequest
from app.api.v2.models.players import Player
from app.services.accounts import AccountRegistrationService
from app.services.captcha import CaptchaService

router = APIRouter()


@router.post("/accounts", status_code=status.HTTP_201_CREATED)
async def register_account(
    request: Request,
    args: RegistrationRequest,
    accounts_service: Annotated[
        AccountRegistrationService,
        Depends(api_dependencies.get_account_registration_service),
    ],
    captcha_service: Annotated[
        CaptchaService,
        Depends(api_dependencies.get_captcha_service),
    ],
) -> Success[Player] | Failure:
    if not await captcha_service.verify(args.captcha_token):
        return responses.failure(
            message="Captcha verification failed.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    errors = await accounts_service.validate_registration(
        username=args.username,
        email=args.email,
        password=args.password,
    )
    if errors:
        message = " ".join(
            error for field_errors in errors.values() for error in field_errors
        )
        return responses.failure(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    registered_account = await accounts_service.create_account(
        username=args.username,
        email=args.email,
        password=args.password,
        request_headers=request.headers,
    )

    response = Player.model_validate(registered_account.player)
    return responses.success(response, status_code=status.HTTP_201_CREATED)
