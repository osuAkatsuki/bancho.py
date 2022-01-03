#!/usr/bin/env python3.9
"""gulag - a fully-featured, dev-centered osu! server implementation
made for running production-quality osu! private servers."""

__author__ = "Joshua Smith (cmyui)"
__email__ = "cmyuiosu@gmail.com"
__discord__ = "cmyui#0425"

import ipaddress
import os

import logging
import uvicorn
from cmyui.logging import Ansi
from cmyui.logging import log
import app.settings
import app.utils


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
            return exit_code

    """ Server should be safe to start """

    # install any debugging hooks from
    # _testing/runtime.py, if present
    app.utils._install_debugging_hooks()

    # check our internet connection status
    if not app.utils.check_connection(timeout=1.5):
        log("No internet connection available.", Ansi.LYELLOW)

    # show info & any contextual warnings.
    app.utils.display_startup_dialog()

    # figure out whether we're using an inet, or unix address
    try:
        ipaddress.ip_address(app.settings.SERVER_ADDR)
    except ValueError:
        if not (
            app.settings.SERVER_PORT is None
            and app.settings.SERVER_ADDR.endswith(".sock")
        ):
            raise ValueError(
                "%r does not appear to be an IPv4, IPv6 or Unix address"
                % app.settings.SERVER_ADDR,
            ) from None

        # unix address
        server_arguments = {"uds": app.settings.SERVER_ADDR}

        # make sure the socket file does not exist on disk and can be bound
        # (uvicorn currently does not do this for us, and will raise an exc)
        if os.path.exists(app.settings.SERVER_ADDR):
            os.remove(app.settings.SERVER_ADDR)
    else:
        # inet address
        server_arguments = {
            "host": app.settings.SERVER_ADDR,
            "port": app.settings.SERVER_PORT,
        }

    # run the server indefinitely
    uvicorn.run(
        "app.api.init_api:asgi_app",
        reload=app.settings.DEBUG,
        log_level=logging.WARNING,
        **server_arguments,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
