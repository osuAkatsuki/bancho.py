from __future__ import annotations

import hashlib
import secrets
import struct
from uuid import UUID

import httpx
import respx
from fastapi import status
from httpx import AsyncClient

import app.packets
import app.state.sessions
from app.packets import ClientPackets
from app.repositories.users import UsersRepository

CHO_HEADERS = {
    "Host": "c.cmyui.xyz",
    "User-Agent": "osu!",
    "CF-Connecting-IP": "127.0.0.1",
}


def _client_packet(packet: ClientPackets, payload: bytes = b"") -> bytes:
    return struct.pack("<HxI", packet, len(payload)) + payload


def _login_body(username: str, password: str) -> bytes:
    client_hash = hashlib.md5(b"bancho-session-test").hexdigest()
    return (
        "\n".join(
            (
                username,
                hashlib.md5(password.encode()).hexdigest(),
                f"b20230814|-5|1|{client_hash}:1.2.3.:{client_hash}:{client_hash}:{client_hash}:|1",
            ),
        ).encode()
        + b"\n"
    )


async def _register_user(http_client: AsyncClient) -> tuple[str, str]:
    suffix = secrets.token_hex(4)
    username = f"test-{suffix}"
    password = "myPassword321$"
    response = await http_client.post(
        "/users",
        headers={
            "Host": "osu.cmyui.xyz",
            "X-Forwarded-For": "127.0.0.1",
            "X-Real-IP": "127.0.0.1",
        },
        data={
            "user[username]": username,
            "user[password]": password,
            "user[user_email]": f"{username}@akatsuki.pw",
            "check": "0",
        },
    )
    assert response.status_code == status.HTTP_200_OK
    return username, password


def _mock_geolocation(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(url__regex=r"http://ip-api\.com/line/.*").mock(
        return_value=httpx.Response(
            status_code=status.HTTP_200_OK,
            content=b"\n".join((b"success", b"CA", b"43.6485", b"-79.4054")),
        ),
    )


async def test_bancho_login_packet_dispatch_and_logout_lifecycle(
    http_client: AsyncClient,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_geolocation(respx_mock)
    username, password = await _register_user(http_client)

    login_response = await http_client.post(
        "/",
        headers=CHO_HEADERS,
        content=_login_body(username, password),
    )

    assert login_response.status_code == status.HTTP_200_OK
    token = login_response.headers["cho-token"]
    UUID(token)
    player = app.state.sessions.players.get(token=token)
    assert player is not None
    assert player.name == username
    assert player.dequeue() == app.packets.bancho_privileges(player.bancho_priv)

    stats_response = await http_client.post(
        "/",
        headers={**CHO_HEADERS, "osu-token": token},
        content=_client_packet(ClientPackets.REQUEST_STATUS_UPDATE),
    )

    assert stats_response.status_code == status.HTTP_200_OK
    assert stats_response.content == app.packets.user_stats(player)

    restarted_response = await http_client.post(
        "/",
        headers={**CHO_HEADERS, "osu-token": "unknown-token"},
        content=b"",
    )

    assert restarted_response.content == (
        app.packets.notification("Server has restarted.")
        + app.packets.restart_server(0)
    )

    player.login_time -= 2
    logout_response = await http_client.post(
        "/",
        headers={**CHO_HEADERS, "osu-token": token},
        content=_client_packet(ClientPackets.LOGOUT, struct.pack("<i", 0)),
    )

    assert logout_response.status_code == status.HTTP_200_OK
    assert player.token == ""
    assert app.state.sessions.players.get(token=token) is None
    assert app.state.sessions.players.get(id=player.id) is None
    assert app.state.sessions.players.get(name=username) is None


async def test_bancho_login_rejects_incorrect_credentials_without_a_session(
    http_client: AsyncClient,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_geolocation(respx_mock)
    username, password = await _register_user(http_client)
    user = await UsersRepository(app.state.services.database).fetch_one(name=username)
    assert user is not None

    response = await http_client.post(
        "/",
        headers=CHO_HEADERS,
        content=_login_body(username, f"incorrect-{password}"),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["cho-token"] == "incorrect-credentials"
    assert app.state.sessions.players.get(id=user.id) is None
    assert app.state.sessions.players.get(name=username) is None
