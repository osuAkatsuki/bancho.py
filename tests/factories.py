from __future__ import annotations

import secrets
from datetime import datetime

from app.repositories.clans import Clan
from app.repositories.maps import Map
from app.repositories.maps import MapServer
from app.repositories.scores import Score
from app.repositories.stats import Stat
from app.repositories.users import User
from app.usecases import dependencies as usecase_dependencies


async def create_user(
    *,
    country: str = "ca",
    preferred_mode: int = 0,
) -> User:
    suffix = secrets.token_hex(4)
    user = await usecase_dependencies.get_repositories().users.create(
        name=f"test-{suffix}",
        email=f"test-{suffix}@akatsuki.pw",
        pw_bcrypt=b"not-a-real-password-hash",
        country=country,
    )

    if preferred_mode:
        updated_user = (
            await usecase_dependencies.get_repositories().users.partial_update(
                id=user["id"],
                preferred_mode=preferred_mode,
            )
        )
        assert updated_user is not None
        user = updated_user

    return user


async def create_player_stats(
    *,
    player_id: int,
    mode: int = 0,
    pp: int = 123,
    plays: int = 7,
) -> Stat:
    await usecase_dependencies.get_repositories().stats.create_all_modes(player_id)

    stat = await usecase_dependencies.get_repositories().stats.partial_update(
        player_id=player_id,
        mode=mode,
        pp=pp,
        plays=plays,
        acc=98.76,
        max_combo=512,
        total_hits=1234,
    )
    assert stat is not None
    return stat


async def create_clan(*, owner_id: int) -> Clan:
    suffix = secrets.token_hex(3)
    return await usecase_dependencies.get_repositories().clans.create(
        name=f"Clan {suffix}",
        tag=suffix.upper(),
        owner=owner_id,
    )


async def create_map(
    *,
    set_id: int | None = None,
    mode: int = 0,
) -> Map:
    map_id = secrets.randbelow(1_000_000) + 1_000_000
    if set_id is None:
        set_id = secrets.randbelow(1_000_000) + 2_000_000

    suffix = secrets.token_hex(4)
    return await usecase_dependencies.get_repositories().maps.create(
        id=map_id,
        server=MapServer.OSU,
        set_id=set_id,
        status=2,
        md5=secrets.token_hex(16),
        artist=f"Artist {suffix}",
        title=f"Title {suffix}",
        version="Insane",
        creator="test",
        filename=f"Artist {suffix} - Title {suffix} (test) [Insane].osu",
        last_update=datetime(2024, 1, 1, 12, 0, 0),
        total_length=180,
        max_combo=512,
        frozen=False,
        plays=3,
        passes=2,
        mode=mode,
        bpm=180.0,
        cs=4.0,
        ar=9.0,
        od=8.0,
        hp=6.0,
        diff=5.25,
    )


async def create_score(
    *,
    player_id: int,
    map_md5: str,
    score: int = 987_654,
    pp: float = 321.45,
    mods: int = 64,
    status: int = 2,
    mode: int = 0,
) -> Score:
    return await usecase_dependencies.get_repositories().scores.create(
        map_md5=map_md5,
        score=score,
        pp=pp,
        acc=98.76,
        max_combo=512,
        mods=mods,
        n300=500,
        n100=12,
        n50=3,
        nmiss=1,
        ngeki=100,
        nkatu=20,
        grade="S",
        status=status,
        mode=mode,
        play_time=datetime(2024, 1, 1, 12, 30, 0),
        time_elapsed=120_000,
        client_flags=0,
        user_id=player_id,
        perfect=0,
        online_checksum=secrets.token_hex(16),
    )
