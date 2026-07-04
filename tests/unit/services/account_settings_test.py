from __future__ import annotations

import hashlib
from types import SimpleNamespace
from typing import Any

import bcrypt

import app.services.account_settings as account_settings
from app._typing import UNSET
from app.repositories.users import User


def _user(**overrides: Any) -> User:
    defaults: dict[str, Any] = {
        "id": 3,
        "name": "cmyui",
        "safe_name": "cmyui",
        "email": "cmyui@akatsuki.pw",
        "priv": 3,
        "country": "ca",
        "silence_end": 0,
        "donor_end": 0,
        "creation_time": 0,
        "latest_activity": 0,
        "clan_id": 0,
        "clan_priv": 0,
        "preferred_mode": 0,
        "play_style": 0,
        "custom_badge_name": None,
        "custom_badge_icon": None,
        "userpage_content": None,
        "api_key": None,
    }
    defaults.update(overrides)
    return User(**defaults)


class _FakeUsersRepository:
    def __init__(
        self,
        user: User,
        taken_names: set[str] | None = None,
        password_hash: str | None = None,
    ) -> None:
        self.user = user
        self.taken_names = taken_names or set()
        self.password_hash = password_hash
        self.partial_updates: list[dict[str, Any]] = []

    async def fetch_password_hash(
        self,
        id: int | None = None,
        name: str | None = None,
    ) -> str | None:
        return self.password_hash

    async def fetch_one(self, name: str | None = None) -> User | None:
        return self.user if name in self.taken_names else None

    async def partial_update(self, id: int, **kwargs: Any) -> User:
        provided = {key: value for key, value in kwargs.items() if value is not UNSET}
        self.partial_updates.append({"id": id, **provided})
        return self.user


class _FakeStatsRepository:
    def __init__(self, pp_by_mode: dict[int, int]) -> None:
        self.pp_by_mode = pp_by_mode

    async def fetch_many(self, player_id: int) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(mode=mode, pp=pp) for mode, pp in self.pp_by_mode.items()
        ]


class _FakeLeaderboardRanksRepository:
    def __init__(self) -> None:
        self.added: list[tuple[int, int, str, float]] = []
        self.removed: list[tuple[int, int, str]] = []

    async def add_to_country_leaderboard(
        self,
        player_id: int,
        mode: int,
        country: str,
        pp: float,
    ) -> None:
        self.added.append((player_id, mode, country, pp))

    async def remove_from_country_leaderboard(
        self,
        player_id: int,
        mode: int,
        country: str,
    ) -> None:
        self.removed.append((player_id, mode, country))


class _FakeAuthenticationService:
    def __init__(self, user: User | None) -> None:
        self.user = user

    async def authenticate_login_credentials(
        self,
        username: str,
        untrusted_password: bytes,
    ) -> User | None:
        return self.user


class _FakeOnlinePlayers:
    def __init__(self, online: SimpleNamespace | None = None) -> None:
        self.online = online

    def get(
        self,
        token: str | None = None,
        id: int | None = None,
        name: str | None = None,
    ) -> SimpleNamespace | None:
        if self.online is not None and self.online.id == id:
            return self.online
        return None


def _service(
    *,
    user: User,
    users_repo: _FakeUsersRepository | None = None,
    ranks_repo: _FakeLeaderboardRanksRepository | None = None,
    pp_by_mode: dict[int, int] | None = None,
    authenticated: bool = True,
    online: SimpleNamespace | None = None,
    password_cache: dict[bytes, bytes] | None = None,
) -> account_settings.AccountSettingsService:
    return account_settings.AccountSettingsService(
        users=users_repo if users_repo is not None else _FakeUsersRepository(user),
        stats=_FakeStatsRepository(pp_by_mode or {}),
        leaderboard_ranks=(
            ranks_repo if ranks_repo is not None else _FakeLeaderboardRanksRepository()
        ),
        authentication=_FakeAuthenticationService(user if authenticated else None),
        online_players=_FakeOnlinePlayers(online),
        password_cache=password_cache if password_cache is not None else {},
        disallowed_names=["mrekk"],
        disallowed_passwords=["password"],
    )


async def test_profile_validation_rejects_invalid_usernames() -> None:
    user = _user()
    service = _service(user=user)

    errors = await service.validate_profile_update(user, username="x")
    assert "username" in errors

    errors = await service.validate_profile_update(user, username="mrekk")
    assert "username" in errors


async def test_profile_validation_rejects_taken_usernames() -> None:
    user = _user()
    users_repo = _FakeUsersRepository(user, taken_names={"taken"})
    service = _service(user=user, users_repo=users_repo)

    errors = await service.validate_profile_update(user, username="taken")
    assert errors["username"] == ["Username already taken by another player."]

    # keeping your current name is always allowed
    users_repo.taken_names.add(user.name)
    errors = await service.validate_profile_update(user, username=user.name)
    assert errors == {}


async def test_profile_validation_rejects_unknown_countries() -> None:
    user = _user()
    service = _service(user=user)

    errors = await service.validate_profile_update(user, country="zz")
    assert "country" in errors

    errors = await service.validate_profile_update(user, country="de")
    assert errors == {}


async def test_profile_validation_rejects_oversized_userpages() -> None:
    user = _user()
    service = _service(user=user)

    errors = await service.validate_profile_update(user, userpage_content="a" * 2049)
    assert "userpage_content" in errors

    errors = await service.validate_profile_update(user, userpage_content="a" * 2048)
    assert errors == {}


async def test_profile_update_only_touches_provided_fields() -> None:
    user = _user()
    users_repo = _FakeUsersRepository(user)
    service = _service(user=user, users_repo=users_repo)

    await service.update_profile(user, userpage_content="hello world")

    assert users_repo.partial_updates == [
        {"id": user.id, "userpage_content": "hello world"},
    ]


async def test_profile_update_allows_clearing_the_userpage() -> None:
    user = _user(userpage_content="hello world")
    users_repo = _FakeUsersRepository(user)
    service = _service(user=user, users_repo=users_repo)

    errors = await service.validate_profile_update(user, userpage_content=None)
    assert errors == {}

    await service.update_profile(user, userpage_content=None)

    assert users_repo.partial_updates == [
        {"id": user.id, "userpage_content": None},
    ]


async def test_profile_update_renames_the_online_session() -> None:
    user = _user()
    online = SimpleNamespace(
        id=user.id,
        name=user.name,
        geoloc={"country": {"acronym": "ca"}},
    )
    service = _service(user=user, online=online)

    await service.update_profile(user, username="cmyui v2", country="de")

    assert online.name == "cmyui v2"
    assert online.geoloc["country"]["acronym"] == "de"


async def test_country_changes_move_country_leaderboard_entries() -> None:
    user = _user(country="ca")
    ranks_repo = _FakeLeaderboardRanksRepository()
    service = _service(
        user=user,
        ranks_repo=ranks_repo,
        pp_by_mode={0: 1234, 4: 2345},
    )

    await service.update_profile(user, country="de")

    assert ranks_repo.removed == [(user.id, 0, "ca"), (user.id, 4, "ca")]
    assert ranks_repo.added == [
        (user.id, 0, "de", 1234),
        (user.id, 4, "de", 2345),
    ]


async def test_restricted_players_are_not_added_to_country_leaderboards() -> None:
    user = _user(country="ca", priv=0)
    ranks_repo = _FakeLeaderboardRanksRepository()
    service = _service(user=user, ranks_repo=ranks_repo, pp_by_mode={0: 1234})

    await service.update_profile(user, country="de")

    assert ranks_repo.removed == [(user.id, 0, "ca")]
    assert ranks_repo.added == []


async def test_password_change_rejects_an_incorrect_current_password() -> None:
    user = _user()
    service = _service(user=user, authenticated=False)

    result = await service.change_password(
        user,
        current_password="wrong",
        new_password="myNewPassword321$",
    )

    assert (
        result.code
        is account_settings.PasswordChangeResultCode.INCORRECT_CURRENT_PASSWORD
    )


async def test_password_change_rejects_weak_new_passwords() -> None:
    user = _user()
    service = _service(user=user)

    result = await service.change_password(
        user,
        current_password="myPassword321$",
        new_password="aaaa",
    )

    assert result.code is account_settings.PasswordChangeResultCode.VALIDATION_FAILED
    assert result.errors


async def test_password_change_updates_the_hash_and_cache() -> None:
    old_md5 = hashlib.md5(b"myPassword321$").hexdigest().encode()
    old_bcrypt = bcrypt.hashpw(old_md5, bcrypt.gensalt())
    user = _user()
    users_repo = _FakeUsersRepository(user, password_hash=old_bcrypt.decode())
    password_cache = {old_bcrypt: old_md5}
    service = _service(
        user=user,
        users_repo=users_repo,
        password_cache=password_cache,
    )

    result = await service.change_password(
        user,
        current_password="myPassword321$",
        new_password="myNewPassword321$",
    )

    assert result.code is account_settings.PasswordChangeResultCode.OK

    (update,) = users_repo.partial_updates
    new_bcrypt = update["pw_bcrypt"]
    new_md5 = hashlib.md5(b"myNewPassword321$").hexdigest().encode()
    assert bcrypt.checkpw(new_md5, new_bcrypt)

    # the old cache entry is dropped and the new hash is cached
    assert old_bcrypt not in password_cache
    assert password_cache[new_bcrypt] == new_md5
