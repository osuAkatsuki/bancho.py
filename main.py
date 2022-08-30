#!/usr/bin/env python3.9
"""main.py - a user-friendly, safe wrapper around bancho.py's runtime

bancho.py is an in-progress osu! server implementation for developers of all levels
of experience interested in hosting their own osu private server instance(s).

the project is developed primarily by the Akatsuki (https://akatsuki.pw) team,
and our aim is to create the most easily maintainable, reliable, and feature-rich
osu! server implementation available.

we're also fully open source!
https://github.com/osuAkatsuki/bancho.py
"""
from __future__ import annotations

__author__ = "Joshua Smith (cmyui)"
__email__ = "cmyuiosu@gmail.com"
__discord__ = "cmyui#0425"

import os

# set working directory to the bancho/ directory.
os.chdir(os.path.dirname(os.path.realpath(__file__)))

import argparse
import logging
import sys
from typing import Sequence

import uvicorn

import app.utils
import app.settings
from app.logging import Ansi
from app.logging import log


def main(argv: Sequence[str]) -> int:
    """Ensure runtime environment is ready, and start the server."""
    app.utils.setup_runtime_environment()

    for safety_check in (
        app.utils.ensure_supported_platform,  # linux only at the moment
        app.utils.ensure_connected_services,  # mysql, redis
        app.utils.ensure_directory_structure,  # .data/ & achievements/ dir structure
        app.utils.ensure_dependencies_and_requirements,  # submodules & oppai-ng built
    ):
        if (exit_code := safety_check()) != 0:
            return exit_code

    """ Parse and handle command-line arguments. """

    parser = argparse.ArgumentParser(
        description=("An open-source osu! server implementation by Akatsuki."),
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s v{app.settings.VERSION}",
    )

    parser.parse_args(argv)

    """ Server should be safe to start """

    # install any debugging hooks from
    # _testing/runtime.py, if present
    app.utils._install_debugging_hooks()

    # check our internet connection status
    if not app.utils.check_connection(timeout=1.5):
        log("No internet connection available.", Ansi.LYELLOW)

    # show info & any contextual warnings.
    app.utils.display_startup_dialog()

    # the server supports both inet and unix sockets.

    if (
        app.utils.is_valid_inet_address(app.settings.SERVER_ADDR)
        and app.settings.SERVER_PORT is not None
    ):
        server_arguments = {
            "host": app.settings.SERVER_ADDR,
            "port": app.settings.SERVER_PORT,
        }
    elif (
        app.utils.is_valid_unix_address(app.settings.SERVER_ADDR)
        and app.settings.SERVER_PORT is None
    ):
        server_arguments = {
            "uds": app.settings.SERVER_ADDR,
        }

        # make sure the socket file does not exist on disk and can be bound
        # (uvicorn currently does not do this for us, and will raise an exc)
        if os.path.exists(app.settings.SERVER_ADDR):
            if (
                app.utils.processes_listening_on_unix_socket(app.settings.SERVER_ADDR)
                != 0
            ):
                log(
                    f"There are other processes listening on {app.settings.SERVER_ADDR}.\n"
                    f"If you've lost it, bancho.py can be killed gracefully with SIGINT.",
                    Ansi.LRED,
                )
                return 1
            else:
                os.remove(app.settings.SERVER_ADDR)
    else:
        raise ValueError(
            "%r does not appear to be an IPv4, IPv6 or Unix address"
            % app.settings.SERVER_ADDR,
        ) from None

    # run the server indefinitely
    uvicorn.run(
        "app.api.init_api:asgi_app",
        reload=app.settings.DEBUG,
        log_level=logging.WARNING,
        server_header=False,
        date_header=False,
        # TODO: uvicorn calls .lower() on the key & value,
        #       but i would prefer Bancho-Version to keep
        #       with standards. perhaps look into this.
        headers=(("bancho-version", app.settings.VERSION),),
        **server_arguments,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
