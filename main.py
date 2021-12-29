#!/usr/bin/env python3.9
"""gulag - a fully-featured, dev-centered osu! server implementation
made for running production-quality osu! private servers."""

__author__ = "Joshua Smith (cmyui)"
__email__ = "cmyuiosu@gmail.com"
__discord__ = "cmyui#0425"

import uvicorn
from cmyui.logging import Ansi
from cmyui.logging import log

import app.settings
import app.utils
from app.api.init_api import asgi_app


def main() -> int:
    """Ensure runtime environment is ready, and start the server."""
    app.utils.setup_runtime_environment()
    for safety_check in (
        app.utils.ensure_supported_platform,  # linux only at the moment
        app.utils.ensure_local_services_are_running,  # mysql (if local)
        app.utils.ensure_directory_structure,  # .data/ & achievements/ dir structure
        app.utils.ensure_dependencies_and_requirements,  # submodules & oppai-ng built
    ):
        if (exit_code := safety_check()) != 0:
            raise SystemExit(exit_code)

    """ Server should be safe to start """

    # install any debugging hooks from
    # _testing/runtime.py, if present
    app.utils._install_debugging_hooks()

    # check our internet connection status
    if not app.utils.check_connection(timeout=1.5):
        log("No internet connection available.", Ansi.LYELLOW)

    # show info & any contextual warnings.
    app.utils.display_startup_dialog()

    uvicorn.run(
        app=asgi_app,  # type: ignore
        host=app.settings.SERVER_ADDR,
        port=app.settings.SERVER_PORT,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
