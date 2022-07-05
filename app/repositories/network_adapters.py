"""
Terminology Reference:

OUI: Organizationally Unique Identifier
    - https://standards-oui.ieee.org/oui/oui.csv
CID: Company ID
    - http://standards-oui.ieee.org/cid/cid.csv
IAB: Individual Address Block
    - http://standards-oui.ieee.org/iab/iab.csv
EUI: Extended Unique Identifier


MA-L: IEEE MAC Address Large (24-bit block size)
MA-M: IEEE MAC Address Large (28-bit block size)
MA-S: IEEE MAC Address Small (36-bit block size)
OUI24: Organizationally Unique Identifier (24-bit block size)
OUI36: Organizationally Unique Identifier (36-bit block size)
IAB: Individual Address Block (36-bit block size)
CID: Company ID Blocks (24-bit block size)
EUI48: Extended Unique Identifier (48-bit block size)
"""
from __future__ import annotations

import csv
import os
import stat
import time
from typing import MutableMapping
from typing import Optional

import app.state.services
from app.objects.network_adapters import OUIEntry

OUI_CACHE_MAX_AGE = 10 * 24 * 60 * 60  # (10 days)
OUI_CSV_URL = "https://standards-oui.ieee.org/oui/oui.csv"
OUI_CSV_CACHE_FILE = ".data/.oui_cache.csv"

## in-memory cache

cache: MutableMapping[str, OUIEntry] = {}


def add_to_cache(oui_entry: OUIEntry) -> None:
    cache[oui_entry.assignment] = oui_entry


def remove_from_cache(oui_entry: OUIEntry) -> None:
    del cache[oui_entry.assignment]


## create

## read


def fetch_oui_info(address: str) -> Optional[OUIEntry]:
    if oui_info := cache.get(address[:6]):
        return oui_info

    return None


def _cache_file_is_usable() -> bool:
    """Return whether we have a usable cache file on disk."""

    # ensure cache file exists & fetch it's metadata
    try:
        stat_result = os.stat(OUI_CSV_CACHE_FILE)
    except (OSError, ValueError):
        return False

    # ensure cache file type is correct
    if not stat.S_ISREG(stat_result.st_mode):
        return False

    # ensure cache data is not stale
    if (time.time() - OUI_CACHE_MAX_AGE) > stat_result.st_mtime:
        return False

    return True


async def fetch_all() -> set[OUIEntry]:
    """Fetch an updated list of OUIs from the IEEE's website."""

    if cache:
        # ram cache (memory) ~100μs
        return set(cache.values())
    else:
        if _cache_file_is_usable():
            # disk cache (filesystem) ~100,000μs
            with open(OUI_CSV_CACHE_FILE) as f:
                oui_csv_data = f.readlines()
        else:
            # no cache (network) ~4,000,000μs
            async with app.state.services.http_client.get(OUI_CSV_URL) as resp:
                assert resp.status == 200
                oui_csv_data = (await resp.read()).decode().splitlines()[1:]

            with open(OUI_CSV_CACHE_FILE, "w") as f:
                f.write("\n".join(oui_csv_data))

        reader = csv.DictReader(
            oui_csv_data,
            fieldnames=(
                "registry",
                "assignment",
                "organization_name",
                "organization_address",
            ),
        )

        oui_entries = set()
        for row in reader:
            oui_entries.add(
                OUIEntry(
                    registry=row["registry"],
                    assignment=row["assignment"],
                    organization_name=row["organization_name"],
                    organization_address=row["organization_address"],
                ),
            )

        return oui_entries


## update

## delete
