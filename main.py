#!/usr/bin/env python3.11
from __future__ import annotations

import logging

import uvicorn

import app.logging
import app.settings
import app.utils

app.logging.configure_logging()


def main() -> int:
    app.utils.display_startup_dialog()
    uvicorn.run(
        "app.api.init_api:asgi_app",
        reload=app.settings.DEBUG,
        log_level=logging.WARNING,
        server_header=False,
        date_header=False,
        headers=[("bancho-version", app.settings.VERSION)],
        host=app.settings.APP_HOST,
        port=app.settings.APP_PORT,
    )
    return 0


if __name__ == "__main__":
    exit(main())
