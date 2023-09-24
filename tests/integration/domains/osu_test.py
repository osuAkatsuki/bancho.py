from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from uuid import UUID

from fastapi import status
from httpx import AsyncClient

from app import encryption


async def test_score_submission(http_client: AsyncClient):
    # ARRANGE

    username = f"test-{secrets.token_hex(4)}"
    email_address = f"cmyui-{secrets.token_hex(4)}@akatsuki.pw"
    passwd_plaintext = "myPassword321$"
    passwd_md5 = hashlib.md5(passwd_plaintext.encode()).hexdigest()

    response = await http_client.post(
        url="/users",
        headers={
            "Host": "osu.cmyui.xyz",
            "X-Forwarded-For": "127.0.0.1",
            "X-Real-IP": "127.0.0.1",
        },
        data={
            "user[username]": username,
            "user[password]": passwd_plaintext,
            "user[user_email]": email_address,
            "check": "0",
        },
    )
    assert response.status_code == status.HTTP_200_OK

    osu_version = "20230814"
    utc_offset = -5
    display_city = 1
    pm_private = 1

    osu_path_md5 = hashlib.md5(b"lol123").hexdigest()
    adapters_str = ".".join(("1", "2", "3")) + "."
    adapters_md5 = hashlib.md5(b"lol123").hexdigest()
    uninstall_md5 = hashlib.md5(b"lol123").hexdigest()  # or uniqueid 1
    disk_signature_md5 = hashlib.md5(b"lol123").hexdigest()  # or uniqueid 2

    client_hashes = (
        ":".join(
            (
                osu_path_md5,
                adapters_str,
                adapters_md5,
                # double md5 unique ids on login; single time on score submission
                hashlib.md5(uninstall_md5.encode()).hexdigest(),
                hashlib.md5(disk_signature_md5.encode()).hexdigest(),
            ),
        )
        + ":"
    )

    login_data = (
        "\n".join(
            (
                username,
                passwd_md5,
                "|".join(
                    (
                        "b" + osu_version,
                        str(utc_offset),
                        str(display_city),
                        client_hashes,
                        str(pm_private),
                    ),
                ),
            ),
        ).encode()
        + b"\n"
    )

    response = await http_client.post(
        url="/",
        headers={
            "Host": "c.cmyui.xyz",
            "User-Agent": "osu!",
            "CF-Connecting-IP": "127.0.0.1",
        },
        content=login_data,
    )
    assert response.status_code == status.HTTP_200_OK

    # cho token must be valid uuid
    try:
        session_token = UUID(response.headers["cho-token"])
    except ValueError:
        raise AssertionError(
            "cho-token is not a valid uuid",
            response.headers["cho-token"],
        )

    has_supporter = True

    beatmap_md5 = "1cf5b2c2edfafd055536d2cefcb89c0e"
    n300 = 83
    n100 = 14
    n50 = 5
    ngeki = 23
    nkatu = 6
    nmiss = 6
    score = 26810
    max_combo = 52
    perfect = False
    grade = "C"
    mods = 136
    passed = True
    game_mode = 0
    client_time = datetime.now()

    storyboard_md5 = hashlib.md5(b"lol123").hexdigest()

    score_online_checksum = hashlib.md5(
        "chickenmcnuggets{0}o15{1}{2}smustard{3}{4}uu{5}{6}{7}{8}{9}{10}{11}Q{12}{13}{15}{14:%y%m%d%H%M%S}{16}{17}".format(
            n100 + n300,
            n50,
            ngeki,
            nkatu,
            nmiss,
            beatmap_md5,
            max_combo,
            perfect,
            username,
            score,
            grade,
            mods,
            passed,
            game_mode,
            client_time,
            osu_version,
            client_hashes,
            storyboard_md5,
            # yyMMddHHmmss
        ).encode(),
    ).hexdigest()

    score_data = [
        beatmap_md5,
        username + (" " if has_supporter else ""),
        score_online_checksum,
        str(n300),
        str(n100),
        str(n50),
        str(ngeki),
        str(nkatu),
        str(nmiss),
        str(score),
        str(max_combo),
        str(perfect),
        str(grade),
        str(mods),
        str(passed),
        str(game_mode),
        client_time.strftime("%y%m%d%H%M%S"),
        str(osu_version),
        "26685362",  # TODO what is this?
    ]

    iv_b64 = b"N2Q1YWZiNzYzNWFiYWZjZWMyMWMwM2QwMDEzOGRiNDk="
    visual_settings_b64 = b"YHD/rr/lajZIr+ZC6UbFYvCOwTOaEF3qhJCFaZUlQA8="

    score_data_b64, client_hash_b64 = encryption.encrypt_score_aes_data(
        score_data,
        client_hashes,
        iv_b64=iv_b64,
        osu_version=osu_version,
    )
    score_time = 13358
    fail_time = 0
    exited_out = False

    # ACT
    response = await http_client.post(
        url="/web/osu-submit-modular-selector.php",
        headers={"Host": "osu.cmyui.xyz", "token": "auth-token"},
        data={
            "x": exited_out,
            "ft": fail_time,
            "fs": visual_settings_b64,
            "bmk": beatmap_md5,  # (`updated_beatmap_hash` in code)
            "sbk": storyboard_md5,
            "iv": iv_b64,
            "c1": f"{uninstall_md5}|{disk_signature_md5}",
            "st": score_time,
            "pass": passwd_md5,
            "osuver": osu_version,
            "s": client_hash_b64,
            # score param
            "score": score_data_b64,
        },
        files={
            # simulate replay data
            "score": b"12345"
            * 100,
        },
    )

    # ASSERT
    assert response.status_code == status.HTTP_200_OK
