from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# all three major captcha providers implement the same
# form-encoded "siteverify" api, so we support each of them.
CAPTCHA_VERIFY_URLS = {
    "recaptcha": "https://www.google.com/recaptcha/api/siteverify",
    "hcaptcha": "https://api.hcaptcha.com/siteverify",
    "turnstile": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
}

PostSiteverify = Callable[[str, dict[str, str]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class CaptchaService:
    provider: str | None
    secret: str | None
    post_siteverify: PostSiteverify

    @property
    def enabled(self) -> bool:
        return self.provider is not None

    async def verify(self, response_token: str | None) -> bool:
        """Verify a captcha response token with the configured provider."""
        if not self.enabled:
            return True

        if not response_token:
            return False

        assert self.provider is not None
        response = await self.post_siteverify(
            CAPTCHA_VERIFY_URLS[self.provider],
            {
                "secret": self.secret or "",
                "response": response_token,
            },
        )
        return response.get("success") is True
