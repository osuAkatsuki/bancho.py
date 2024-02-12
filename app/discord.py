"""Functionality related to Discord interactivity."""

from __future__ import annotations

from typing import Any

import orjson
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from app.state import services

# NOTE: this module currently only implements discord webhooks

__all__ = (
    "Footer",
    "Image",
    "Thumbnail",
    "Video",
    "Provider",
    "Author",
    "Field",
    "Embed",
    "Webhook",
)


class Footer:
    def __init__(self, text: str, **kwargs: Any) -> None:
        self.text = text
        self.icon_url = kwargs.get("icon_url")
        self.proxy_icon_url = kwargs.get("proxy_icon_url")


class Image:
    def __init__(self, **kwargs: Any) -> None:
        self.url = kwargs.get("url")
        self.proxy_url = kwargs.get("proxy_url")
        self.height = kwargs.get("height")
        self.width = kwargs.get("width")


class Thumbnail:
    def __init__(self, **kwargs: Any) -> None:
        self.url = kwargs.get("url")
        self.proxy_url = kwargs.get("proxy_url")
        self.height = kwargs.get("height")
        self.width = kwargs.get("width")


class Video:
    def __init__(self, **kwargs: Any) -> None:
        self.url = kwargs.get("url")
        self.height = kwargs.get("height")
        self.width = kwargs.get("width")


class Provider:
    def __init__(self, **kwargs: str) -> None:
        self.url = kwargs.get("url")
        self.name = kwargs.get("name")


class Author:
    def __init__(self, **kwargs: str) -> None:
        self.name = kwargs.get("name")
        self.url = kwargs.get("url")
        self.icon_url = kwargs.get("icon_url")
        self.proxy_icon_url = kwargs.get("proxy_icon_url")


class Field:
    def __init__(self, name: str, value: str, inline: bool = False) -> None:
        self.name = name
        self.value = value
        self.inline = inline


class Embed:
    def __init__(self, **kwargs: Any) -> None:
        self.title = kwargs.get("title")
        self.type = kwargs.get("type")
        self.description = kwargs.get("description")
        self.url = kwargs.get("url")
        self.timestamp = kwargs.get("timestamp")  # datetime
        self.color = kwargs.get("color", 0x000000)

        self.footer: Footer | None = kwargs.get("footer")
        self.image: Image | None = kwargs.get("image")
        self.thumbnail: Thumbnail | None = kwargs.get("thumbnail")
        self.video: Video | None = kwargs.get("video")
        self.provider: Provider | None = kwargs.get("provider")
        self.author: Author | None = kwargs.get("author")

        self.fields: list[Field] = kwargs.get("fields", [])

    def set_footer(self, **kwargs: Any) -> None:
        self.footer = Footer(**kwargs)

    def set_image(self, **kwargs: Any) -> None:
        self.image = Image(**kwargs)

    def set_thumbnail(self, **kwargs: Any) -> None:
        self.thumbnail = Thumbnail(**kwargs)

    def set_video(self, **kwargs: Any) -> None:
        self.video = Video(**kwargs)

    def set_provider(self, **kwargs: Any) -> None:
        self.provider = Provider(**kwargs)

    def set_author(self, **kwargs: Any) -> None:
        self.author = Author(**kwargs)

    def add_field(self, name: str, value: str, inline: bool = False) -> None:
        self.fields.append(Field(name, value, inline))


class Webhook:
    """A class to represent a single-use Discord webhook."""

    def __init__(self, url: str, **kwargs: Any) -> None:
        self.url = url
        self.content = kwargs.get("content")
        self.username = kwargs.get("username")
        self.avatar_url = kwargs.get("avatar_url")
        self.tts = kwargs.get("tts")
        self.file = kwargs.get("file")
        self.embeds = kwargs.get("embeds", [])

    def add_embed(self, embed: Embed) -> None:
        self.embeds.append(embed)

    @property
    def json(self) -> Any:
        if not any([self.content, self.file, self.embeds]):
            raise Exception(
                "Webhook must contain at least one " "of (content, file, embeds).",
            )

        if self.content and len(self.content) > 2000:
            raise Exception("Webhook content must be under " "2000 characters.")

        payload: dict[str, Any] = {"embeds": []}

        for key in ("content", "username", "avatar_url", "tts", "file"):
            val = getattr(self, key)
            if val is not None:
                payload[key] = val

        for embed in self.embeds:
            embed_payload = {}

            # simple params
            for key in ("title", "type", "description", "url", "timestamp", "color"):
                val = getattr(embed, key)
                if val is not None:
                    embed_payload[key] = val

            # class params, must turn into dict
            for key in ("footer", "image", "thumbnail", "video", "provider", "author"):
                val = getattr(embed, key)
                if val is not None:
                    embed_payload[key] = val.__dict__

            if embed.fields:
                embed_payload["fields"] = [f.__dict__ for f in embed.fields]

            payload["embeds"].append(embed_payload)

        return orjson.dumps(payload, default=str).decode()

    @retry(
        stop=stop_after_attempt(10),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def post(self) -> None:
        """Post the webhook in JSON format."""
        # TODO: if `self.file is not None`, then we should
        #       use multipart/form-data instead of json payload.
        headers = {"Content-Type": "application/json"}
        response = await services.http_client.post(
            self.url,
            content=self.json,
            headers=headers,
        )
        response.raise_for_status()
