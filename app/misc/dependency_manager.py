import importlib
from typing import AsyncGenerator

import cmyui
from cmyui.logging import Ansi
from cmyui.logging import log
from objects import glob


async def _get_latest_dependency_versions() -> AsyncGenerator[
    tuple[str, cmyui.Version, cmyui.Version],
    None,
]:
    """Return the current installed & latest version for each dependency."""
    with open("requirements.txt") as f:
        dependencies = f.read().splitlines(keepends=False)

    for dependency in dependencies:
        current_ver_str = importlib.metadata.version(dependency)
        current_ver = cmyui.Version.from_str(current_ver_str)

        if not current_ver:
            # the module uses some more advanced (and often hard to parse)
            # versioning system, so we won't be able to report updates.
            continue

        # TODO: split up and do the requests asynchronously
        url = f"https://pypi.org/pypi/{dependency}/json"
        async with glob.http_session.get(url) as resp:
            if resp.status == 200 and (json := await resp.json()):
                latest_ver = cmyui.Version.from_str(json["info"]["version"])

                if not latest_ver:
                    # they've started using a more advanced versioning system.
                    continue

                yield (dependency, latest_ver, current_ver)
            else:
                yield (dependency, current_ver, current_ver)


async def check_for_dependency_updates() -> None:
    """Notify the developer of any dependency updates available."""
    updates_available = False

    async for module, current_ver, latest_ver in _get_latest_dependency_versions():
        if latest_ver > current_ver:
            updates_available = True
            log(
                f"{module} has an update available "
                f"[{current_ver!r} -> {latest_ver!r}]",
                Ansi.LMAGENTA,
            )

    if updates_available:
        log(
            "Python modules can be updated with "
            "`python3.9 -m pip install -U <modules>`.",
            Ansi.LMAGENTA,
        )
