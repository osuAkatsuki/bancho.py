from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Mapping

import aiohttp

import app.packets
import app.settings
import app.state.cache
import app.state.services
import app.state.sessions
import app.utils
from app.constants import regexes


async def osu_registration(
    player_name: str,
    email: str,
    pw_plaintext: str,
    check_breaches: bool = True,
) -> Mapping[str, list[str]]:
    """Perform validation on a player registration."""
    # ensure all args passed
    # are safe for registration.
    errors: Mapping[str, list[str]] = defaultdict(list)

    ## Usernames must:
    # - be within 2-15 characters in length
    # - not contain both ' ' and '_', one is fine
    # - not be in the config's `disallowed_names` list
    # - not already be taken by another player
    if not regexes.USERNAME.match(player_name):
        errors["username"].append("Username must be 2-15 characters in length.")

    if "_" in player_name and " " in player_name:
        errors["username"].append('Username may contain "_" and " ", but not both.')

    if player_name in app.settings.DISALLOWED_NAMES:
        errors["username"].append("Username disallowed.")

    if "username" not in errors:
        # TODO move to repositories
        if await app.state.services.database.fetch_one(
            "SELECT 1 FROM users WHERE safe_name = :safe_name",
            {"safe_name": player_name.lower().replace(" ", "_")},
        ):
            errors["username"].append("Username already taken by another player.")

    ## Emails must:
    # - match the regex `^[^@\s]{1,200}@[^@\s\.]{1,30}\.[^@\.\s]{1,24}$`
    # - not already be taken by another player
    if regexes.EMAIL.match(email):
        if await app.state.services.database.fetch_one(
            "SELECT 1 FROM users WHERE email = :email",
            {"email": email},
        ):
            errors["user_email"].append("Email already taken by another player.")
    else:
        errors["user_email"].append("Email syntax invalid.")

    ## Passwords must:
    # - be within 8-72 characters in length
    #   NOTE: the osu! client can only send 50 characters
    #   NOTE: 72 character limit is because of bcrypt usage
    #   https://www.openwall.com/lists/oss-security/2012/01/02/4
    # - have more than 3 unique characters
    # - not be a breached password in a pwnedpasswords.com database
    if not 8 <= len(pw_plaintext) <= 72:
        errors["password"].append("Password must be 8-72 characters in length.")

    if len(set(pw_plaintext)) <= 3:
        errors["password"].append("Password must have more than 3 unique characters.")

    # check if password is compromised
    pw_sha1 = hashlib.sha1(pw_plaintext.encode("utf-8")).hexdigest().upper()
    hash_prefix = pw_sha1[:5]

    if check_breaches:
        try:
            async with app.state.services.http_client.get(
                f"https://api.pwnedpasswords.com/range/{hash_prefix}",
                headers={"User-Agent": f"bancho.py v{app.settings.VERSION}"},
            ) as resp:
                resp_body = await resp.text()
        except aiohttp.ClientConnectionError:
            pass
        else:
            breached_hashes = {
                hash_prefix + suffix: int(count)
                for suffix, count in (
                    line.split(":", 1) for line in resp_body.splitlines()
                )
            }

            if breach_count := breached_hashes.get(pw_sha1):
                errors["password"].append(
                    f"Password has been breached ({breach_count} times).",
                )

    return errors
