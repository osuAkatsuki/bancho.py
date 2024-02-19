from __future__ import annotations

import time
from collections.abc import Collection
from functools import cache

import app.packets
from app.constants.mods import Mods
from app.constants.multiplayer import MatchTeams
from app.constants.multiplayer import SlotStatus
from app.constants.osu_client_details import OsuStream
from app.constants.privileges import Privileges
from app.errors import Error
from app.errors import ErrorCode
from app.logging import log
from app.repositories import channel_memberships as channel_memberships_repo
from app.repositories import channels as channels_repo
from app.repositories import multiplayer_matches as matches_repo
from app.repositories import multiplayer_slots as multiplayer_slots_repo
from app.repositories import osu_sessions as osu_sessions_repo
from app.repositories import users as users_repo
from app.repositories.channel_memberships import GrantType
from app.repositories.multiplayer_matches import MatchTeamTypes
from app.repositories.multiplayer_matches import MultiplayerMatch
from app.repositories.multiplayer_slots import MatchSlot
from app.repositories.osu_sessions import OsuSession
from app.repositories.users import User

MULTIPLAYER_MATCH_CREATION_LOCK_KEY = "bancho:multiplayer_match_creation_lock"


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
    # TODO: ensure password joining works on initial match creation
    #       (there has been some logic changed here from origin/master)
    if untrusted_password != multiplayer_match["password"]:
        return Error(
            user_feedback="Invalid password.",
            error_code=ErrorCode.INVALID_REQUEST,
        )

    async with app.state.services.redis.lock(
        name=MULTIPLAYER_MATCH_CREATION_LOCK_KEY,
        timeout=5.0,
    ):
        match_slot_id = await multiplayer_slots_repo.reserve_match_slot_id(
            match_id=multiplayer_match["match_id"],
        )
        if match_slot_id is None:
            return Error(
                user_feedback="Failed to reserve a match slot.",
                error_code=ErrorCode.INTERNAL_SERVER_ERROR,
            )

        match_slot = await multiplayer_slots_repo.create(
            match_id=multiplayer_match["match_id"],
            slot_id=match_slot_id,
            user_id=osu_session["user_id"],
            session_id=osu_session["session_id"],
            status=SlotStatus.OPEN,
            team=MatchTeams.NEUTRAL,
            mods=Mods.NOMOD,
            loaded=False,
            skipped=False,
        )

    # 3. join the multiplayer channel
    await channel_memberships_repo.create(
        session_id=osu_session["session_id"],
        channel_name=f"#multi_{multiplayer_match['match_id']}",
        grant_type=GrantType.IMPLICIT,
    )

    # 4. leave the #lobby channel
    await channel_memberships_repo.revoke(
        session_id=osu_session["session_id"],
        channel_name="#lobby",
    )

    # 5. assign them a team if it's team-vs
    if multiplayer_match["team_type"] is MatchTeamTypes.TEAM_VS:
        maybe_slot = await multiplayer_slots_repo.partial_update(
            match_id=multiplayer_match["match_id"],
            slot_id=match_slot["slot_id"],
            team=MatchTeams.RED,
        )
        assert maybe_slot is not None
        match_slot = maybe_slot

    # 6. update osu session to have the match info
    maybe_session = await osu_sessions_repo.partial_update(
        session_id=osu_session["session_id"],
        match_id=multiplayer_match["match_id"],
    )
    assert maybe_session is not None
    osu_session = maybe_session

    return None


async def leave_multiplayer_match(
    session_id: str | OsuSession,
    multiplayer_match_id: int,
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

    # 1. remove the slot from the match
    match_slot = await multiplayer_slots_repo.fetch_user_slot_in_match(
        match_id=multiplayer_match["match_id"],
        user_id=osu_session["user_id"],
    )
    if match_slot is None:
        return Error(
            user_feedback="You are not in the match.",
            error_code=ErrorCode.INVALID_REQUEST,
        )

    maybe_slot = await multiplayer_slots_repo.delete(
        match_id=multiplayer_match["match_id"],
        slot_id=match_slot["slot_id"],
    )
    assert maybe_slot is not None
    match_slot = maybe_slot

    # 2. leave the multiplayer channel
    await channel_memberships_repo.revoke(
        session_id=osu_session["session_id"],
        channel_name=f"#multi_{multiplayer_match['match_id']}",
    )

    # 3. if the multi is now empty, delete it & inform lobby
    match_slots = await multiplayer_slots_repo.fetch_all_for_match(
        match_id=multiplayer_match["match_id"],
    )
    if not match_slots:
        maybe_match = await matches_repo.delete(match_id=multiplayer_match["match_id"])
        assert maybe_match is not None
        multiplayer_match = maybe_match

        # inform the lobby of the match deletion
        lobby_channel_memberships = await channel_memberships_repo.fetch_all(
            channel_name=f"#lobby",
        )
        await osu_sessions_repo.multicast_osu_data(
            target_session_ids={m["session_id"] for m in lobby_channel_memberships},
            data=app.packets.dispose_match(id=multiplayer_match["match_id"]),
        )

    # - otherwise, if the user was host/ref, transfer/remove it
    else:

        def determine_new_host_user_id(
            match_slots: Collection[MatchSlot],
        ) -> int | None:
            for slot in match_slots:
                if slot["user_id"] is not None:
                    return slot["user_id"]
            return None

        if osu_session["user_id"] == multiplayer_match["host_id"]:
            new_host_user_id = determine_new_host_user_id(match_slots.values())
            assert new_host_user_id is not None

            maybe_match = await matches_repo.partial_update(
                match_id=multiplayer_match["match_id"],
                host_id=new_host_user_id,
            )
            assert maybe_match is not None
            multiplayer_match = maybe_match

        if osu_session["user_id"] in multiplayer_match["referees"]:
            maybe_match = await matches_repo.partial_update(
                match_id=multiplayer_match["match_id"],
                referees=multiplayer_match["referees"] - {osu_session["user_id"]},
            )
            assert maybe_match is not None
            multiplayer_match = maybe_match

        slot_statuses: list[int] = []
        slot_teams: list[int] = []
        slot_user_ids: list[int | None] = []
        slot_mods: list[int] = []
        for slot_id in range(16):
            slot = match_slots.get(str(slot_id))
            if slot is not None:
                slot_statuses.append(slot["status"].value)
                slot_teams.append(slot["team"].value)
                slot_user_ids.append(slot["user_id"])
                slot_mods.append(slot["mods"].value)
            else:
                slot_statuses.append(SlotStatus.OPEN.value)
                slot_teams.append(MatchTeams.NEUTRAL.value)
                slot_user_ids.append(None)
                slot_mods.append(Mods.NOMOD.value)

        await osu_sessions_repo.multicast_osu_data(
            target_session_ids={s["session_id"] for s in match_slots.values()},
            data=app.packets.update_match(
                match_id=multiplayer_match["match_id"],
                in_progress=multiplayer_match["in_progress"],
                mods=multiplayer_match["mods"],
                name=multiplayer_match["name"],
                passwd=multiplayer_match["password"],
                map_name=multiplayer_match["map_name"],
                map_id=multiplayer_match["map_id"],
                map_md5=multiplayer_match["map_md5"],
                slot_statuses=slot_statuses,
                slot_teams=slot_teams,
                slot_user_ids=slot_user_ids,
                host_id=multiplayer_match["host_id"],
                mode=multiplayer_match["mode"],
                win_condition=multiplayer_match["win_condition"],
                team_type=multiplayer_match["team_type"],
                freemods=multiplayer_match["freemods"],
                slot_mods=slot_mods,
                seed=multiplayer_match["seed"],
                include_plaintext_password_in_data=True,
            ),
        )

    # 4. update osu session to have no match info

    # 5. enqueue new match state if match still exists
