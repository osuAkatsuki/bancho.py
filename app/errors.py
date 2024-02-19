from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    INTERNAL_SERVER_ERROR = "internal_server_error"
    RESOURCE_NOT_FOUND = "resource_not_found"


class Error(BaseModel):
    user_feedback: str
    error_code: ErrorCode
