from __future__ import annotations

import time
from functools import cache

import app.packets
from app.constants.osu_client_details import OsuStream
from app.constants.privileges import Privileges
from app.errors import Error
from app.errors import ErrorCode
from app.logging import log
from app.repositories import channel_memberships as channel_memberships_repo
from app.repositories import channels as channels_repo
from app.repositories import multiplayer_matches as matches_repo
from app.repositories import osu_sessions as osu_sessions_repo
from app.repositories import users as users_repo
from app.repositories.channel_memberships import GrantType
from app.repositories.multiplayer_matches import MatchTeamTypes
from app.repositories.multiplayer_matches import MutliplayerMatch
from app.repositories.osu_sessions import OsuSession
from app.repositories.users import User


@cache
def is_restricted(server_privileges: Privileges | int) -> bool:
    return server_privileges & Privileges.UNRESTRICTED == 0


@cache
def has_verified_account(server_privileges: Privileges | int) -> bool:
    return server_privileges & Privileges.VERIFIED != 0


def is_silenced(silence_end: int) -> bool:
    return silence_end >= time.time()


async def add_privileges(
    user_id: int | User,
    privileges_to_add: Privileges,
) -> None | Error:
    if isinstance(user_id, int):
        user = await users_repo.fetch_one(id=user_id)
        if user is None:
            return Error(
                user_feedback="User not found.",
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
            )
    else:
        user = user_id

    new_privileges = user["priv"] | privileges_to_add

    # update privs for user
    maybe_user = await users_repo.partial_update(id=user["id"], priv=new_privileges)
    if maybe_user is None:
        return Error(
            user_feedback="Failed to add privileges.",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )
    user = maybe_user

    # update privs for all active osu sessions
    osu_sessions = await osu_sessions_repo.fetch_all(user_id=user["id"])
    for session in osu_sessions:
        await osu_sessions_repo.partial_update(
            session_id=session["session_id"],
            priv=Privileges(new_privileges),  # TODO: serialize() and deserializ
        )


async def resolve_session_id(session_id: str | OsuSession) -> OsuSession | None:
    if isinstance(session_id, str):
        session = await osu_sessions_repo.fetch_one(session_id=session_id)
        if session is None:
            return None
        return session
    else:
        return session_id


async def add_spectator(
    host_session_id: str | OsuSession,
    spectator_session_id: str | OsuSession,
) -> None | Error:
    host_session = await resolve_session_id(host_session_id)
    if host_session is None:
        return Error(
            user_feedback="Host session not found.",
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
        )

    spectator_session = await resolve_session_id(spectator_session_id)
    if spectator_session is None:
        return Error(
            user_feedback="Spectator session not found.",
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
        )

    if spectator_session["user_id"] not in host_session["spectator_session_ids"]:
        return Error(
            user_feedback="Spectator is not spectating the host.",
            error_code=ErrorCode.INVALID_REQUEST,
        )

    spectator_channel = await channels_repo.fetch_one(
        name=f"#spect_{host_session['user_id']}",
    )
    if spectator_channel is None:
        spectator_channel = await channels_repo.create(
            name=f"#spect_{host_session['user_id']}",
            topic=f"Spectating {host_session['name']}",
            read_priv=Privileges.UNRESTRICTED,
            write_priv=Privileges.UNRESTRICTED,
            auto_join=False,
            instance=False,
        )

        # add the host to the channel
        await channel_memberships_repo.create(
            session_id=host_session["session_id"],
            channel_name=spectator_channel["name"],
            grant_type=GrantType.IMPLICIT,
        )

    # add the spectator to the channel
    await channel_memberships_repo.create(
        session_id=spectator_session["session_id"],
        channel_name=spectator_channel["name"],
        grant_type=GrantType.IMPLICIT,
    )

    maybe_session = await osu_sessions_repo.partial_update(
        session_id=host_session["session_id"],
        spectator_session_ids=(
            host_session["spectator_session_ids"] | {spectator_session["user_id"]}
        ),
    )
    assert maybe_session is not None
    host_session = maybe_session

    maybe_session = await osu_sessions_repo.partial_update(
        session_id=spectator_session["session_id"],
        spectating_session_id=host_session["session_id"],
    )
    assert maybe_session is not None
    spectator_session = maybe_session

    new_channel_memberships = await channel_memberships_repo.fetch_all(
        channel_name=spectator_channel["name"],
    )
    new_channel_info_packet = app.packets.channel_info(
        spectator_channel["name"],
        spectator_channel["topic"],
        len(new_channel_memberships),
    )
    await osu_sessions_repo.unicast_osu_data(
        target_session_id=host_session["session_id"],
        data=new_channel_info_packet,
    )
    await osu_sessions_repo.multicast_osu_data(
        target_session_ids=host_session["spectator_session_ids"],
        data=(
            new_channel_info_packet
            + app.packets.fellow_spectator_joined(spectator_session["user_id"])
        ),
    )

    await osu_sessions_repo.unicast_osu_data(
        target_session_id=spectator_session["session_id"],
        data=app.packets.spectator_joined(host_session["user_id"]),
    )

    log(
        "{spectator} is now spectating {host}.".format(
            spectator=f"{spectator_session['name']} ({spectator_session['user_id']})",
            host=f"{host_session['name']} ({host_session['user_id']})",
        ),
    )


async def remove_spectator(
    host_session_id: str | OsuSession,
    spectator_session_id: str | OsuSession,
) -> None | Error:
    host_session = await resolve_session_id(host_session_id)
    if host_session is None:
        return Error(
            user_feedback="Host session not found.",
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
        )

    spectator_session = await resolve_session_id(spectator_session_id)
    if spectator_session is None:
        return Error(
            user_feedback="Spectator session not found.",
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
        )

    if spectator_session["user_id"] not in host_session["spectator_session_ids"]:
        return Error(
            user_feedback="Spectator is not spectating the host.",
            error_code=ErrorCode.INVALID_REQUEST,
        )

    maybe_session = await osu_sessions_repo.partial_update(
        session_id=host_session["session_id"],
        spectator_session_ids=(
            host_session["spectator_session_ids"] - {spectator_session["user_id"]}
        ),
    )
    assert maybe_session is not None
    host_session = maybe_session

    maybe_session = await osu_sessions_repo.partial_update(
        session_id=spectator_session["session_id"],
        spectating_session_id=None,
    )
    assert maybe_session is not None
    spectator_session = maybe_session

    # fetch #spectator channel
    spectator_channel = await channels_repo.fetch_one(
        name=f"#spect_{host_session['user_id']}",
    )
    if spectator_channel is None:
        return Error(
            user_feedback="Spectator channel not found.",
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
        )

    # leave the channel
    await channel_memberships_repo.revoke(
        session_id=spectator_session["session_id"],
        channel_name=spectator_channel["name"],
    )

    if not host_session["spectator_session_ids"]:
        await channels_repo.delete(name=spectator_channel["name"])
    else:
        new_channel_memberships = await channel_memberships_repo.fetch_all(
            channel_name=spectator_channel["name"],
        )
        new_channel_info_packet = app.packets.channel_info(
            spectator_channel["name"],
            spectator_channel["topic"],
            len(new_channel_memberships),
        )
        await osu_sessions_repo.unicast_osu_data(
            target_session_id=host_session["session_id"],
            data=new_channel_info_packet,
        )
        await osu_sessions_repo.multicast_osu_data(
            target_session_ids=host_session["spectator_session_ids"],
            data=(
                new_channel_info_packet
                + app.packets.fellow_spectator_left(spectator_session["user_id"])
            ),
        )

    await osu_sessions_repo.unicast_osu_data(
        target_session_id=spectator_session["session_id"],
        data=app.packets.spectator_left(host_session["user_id"]),
    )

    log(
        "{spectator} is no longer spectating {host}.".format(
            spectator=f"{spectator_session['name']} ({spectator_session['user_id']})",
            host=f"{host_session['name']} ({host_session['user_id']})",
        ),
    )


async def join_multiplayer_match(
    session_id: str | OsuSession,
    multiplayer_match_id: int,
    untrusted_password: str,
) -> None | Error:
    osu_session = await resolve_session_id(session_id)
    if osu_session is None:
        return Error(
            user_feedback="Host session not found.",
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
        )

    multiplayer_match = await matches_repo.fetch_one(match_id=multiplayer_match_id)
    if multiplayer_match is None:
        return Error(
            user_feedback="Match not found.",
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
        )

    # 1. ensure our account does not already have a session in the match
    if (
        not osu_session["is_tourney_client"]
        and osu_session["user_id"] in multiplayer_match["tourney_client_user_ids"]
    ):
        return Error(
            user_feedback=(
                "You cannot have a tourney client "
                "and non-tourney client in the same match."
            ),
            error_code=ErrorCode.INVALID_REQUEST,
        )

    # 2. if the joining user is host, they're creating the match. give them slot 0.
    if osu_session["user_id"] == multiplayer_match["host_id"]:
        new_slot_id = "TODO"
    # - otherwise, they're just joining. verify their passwd, find a slot for them
    else:
        if untrusted_password != multiplayer_match["password"]:
            return Error(
                user_feedback="Invalid password.",
                error_code=ErrorCode.INVALID_REQUEST,
            )

        new_slot_id = "TODO"

    # 3. join the multiplayer channel
    await channel_memberships_repo.create(
        session_id=osu_session["session_id"],
        channel_name=f"#multi_{multiplayer_match['id']}",
        grant_type=GrantType.IMPLICIT,
    )
    # 4. leave the #lobby channel
    await channel_memberships_repo.revoke(
        session_id=osu_session["session_id"],
        channel_name="#lobby",
    )
    # 5. assign them a team if it's team-vs
    if multiplayer_match["team_type"] is MatchTeamTypes.TEAM_VS:
        ...  # TODO

    # 6. update slot & player to have the match info
    # 7. enqueue new match state to all the players in it, and in #lobby


async def leave_multiplayer_match(
    host_session_id: str | OsuSession,
    multiplayer_match_id: int,
) -> None | Error:
    host_session = await resolve_session_id(host_session_id)
    if host_session is None:
        return Error(
            user_feedback="Host session not found.",
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
        )

    multiplayer_match = await matches_repo.fetch_one(match_id=multiplayer_match_id)
    if multiplayer_match is None:
        return Error(
            user_feedback="Match not found.",
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
        )
