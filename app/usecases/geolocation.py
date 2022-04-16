from __future__ import annotations

from typing import Optional

import app.objects.geolocation
import app.state.services
from app._typing import IPAddress
from app.logging import Ansi
from app.logging import log


def lookup_maxmind(ip: IPAddress) -> app.objects.geolocation.Geolocation:
    """Fetch geolocation data based on ip (using local db)."""
    assert app.state.services.geoloc_db is not None

    res = app.state.services.geoloc_db.city(ip)

    if res.country.iso_code is not None:
        acronym = res.country.iso_code.lower()
    else:
        acronym = "XX"

    return {
        "latitude": res.location.latitude or 0.0,
        "longitude": res.location.longitude or 0.0,
        "country": {
            "acronym": acronym,
            "numeric": country_codes[acronym],
        },
    }


async def lookup_ipinfo(ip: IPAddress) -> Optional[app.objects.geolocation.Geolocation]:
    """Fetch geolocation data based on ip (using ip-api)."""
    url = f"http://ip-api.com/line/{ip}"

    async with app.state.services.http.get(url) as resp:
        if not resp or resp.status != 200:
            log("Failed to get geoloc data: request failed.", Ansi.LRED)
            return None

        status, *lines = (await resp.text()).split("\n")

        if status != "success":
            err_msg = lines[0]
            if err_msg == "invalid query":
                err_msg += f" ({url})"

            log(f"Failed to get geoloc data: {err_msg}.", Ansi.LRED)
            return None

    acronym = lines[1].lower()

    return {
        "latitude": float(lines[6]),
        "longitude": float(lines[7]),
        "country": {
            "acronym": acronym,
            "numeric": country_codes[acronym],
        },
    }


async def lookup(ip: IPAddress) -> Optional[app.objects.geolocation.Geolocation]:
    """Fetch geolocation data based on ip."""
    if not ip.is_private:
        if app.state.services.geoloc_db is not None:
            # decent case, dev has downloaded a geoloc db from
            # maxmind, so we can do a local db lookup. (~1-5ms)
            # https://www.maxmind.com/en/home
            geoloc = lookup_maxmind(ip)
        else:
            # worst case, we must do an external db lookup
            # using a public api. (depends, `ping ip-api.com`)
            geoloc = await lookup_ipinfo(ip)

        if geoloc is not None:
            return geoloc

    return None
