from __future__ import annotations

from typing import Any

from app.services.captcha import CAPTCHA_VERIFY_URLS
from app.services.captcha import CaptchaService


class _FakeSiteverify:
    def __init__(self, success: bool) -> None:
        self.success = success
        self.calls: list[tuple[str, dict[str, str]]] = []

    async def __call__(self, url: str, data: dict[str, str]) -> dict[str, Any]:
        self.calls.append((url, data))
        return {"success": self.success}


async def test_captcha_service_accepts_anything_when_disabled() -> None:
    siteverify = _FakeSiteverify(success=False)
    service = CaptchaService(
        provider=None,
        secret=None,
        post_siteverify=siteverify,
    )

    assert await service.verify(None) is True
    assert await service.verify("some-token") is True
    assert siteverify.calls == []


async def test_captcha_service_requires_a_token_when_enabled() -> None:
    siteverify = _FakeSiteverify(success=True)
    service = CaptchaService(
        provider="turnstile",
        secret="my-secret",
        post_siteverify=siteverify,
    )

    assert await service.verify(None) is False
    assert await service.verify("") is False
    assert siteverify.calls == []


async def test_captcha_service_verifies_tokens_with_the_provider() -> None:
    siteverify = _FakeSiteverify(success=True)
    service = CaptchaService(
        provider="recaptcha",
        secret="my-secret",
        post_siteverify=siteverify,
    )

    assert await service.verify("player-response-token") is True
    assert siteverify.calls == [
        (
            CAPTCHA_VERIFY_URLS["recaptcha"],
            {"secret": "my-secret", "response": "player-response-token"},
        ),
    ]


async def test_captcha_service_rejects_failed_verifications() -> None:
    siteverify = _FakeSiteverify(success=False)
    service = CaptchaService(
        provider="hcaptcha",
        secret="my-secret",
        post_siteverify=siteverify,
    )

    assert await service.verify("player-response-token") is False
