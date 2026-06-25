from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import bcrypt

from app.constants.privileges import Privileges
from app.repositories.client_hashes import ClientHashesRepository
from app.repositories.client_hashes import ClientHashWithPlayer
from app.repositories.ingame_logins import IngameLoginsRepository
from app.repositories.mail import MailRepository
from app.repositories.mail import MailWithUsernames
from app.repositories.users import User
from app.repositories.users import UsersRepository


@dataclass(frozen=True)
class BanchoLoginService:
    users: UsersRepository
    ingame_logins: IngameLoginsRepository
    client_hashes: ClientHashesRepository
    mail: MailRepository
    password_cache: dict[bytes, bytes]

    async def authenticate(
        self,
        username: str,
        untrusted_password: bytes,
    ) -> User | None:
        user_info = await self.users.fetch_one(
            name=username,
            fetch_all_fields=True,
        )
        if user_info is None:
            return None

        trusted_hashword = user_info["pw_bcrypt"].encode()

        # in-memory bcrypt lookup cache for performance
        if trusted_hashword in self.password_cache:  # ~0.01 ms
            if untrusted_password != self.password_cache[trusted_hashword]:
                return None
        else:  # ~200ms
            if not bcrypt.checkpw(untrusted_password, trusted_hashword):
                return None

            self.password_cache[trusted_hashword] = untrusted_password

        return user_info

    async def record_login(
        self,
        *,
        user_id: int,
        ip: str,
        osu_version: date,
        osu_stream: str,
    ) -> None:
        await self.ingame_logins.create(
            user_id=user_id,
            ip=ip,
            osu_ver=osu_version,
            osu_stream=osu_stream,
        )

    async def record_client_hashes(
        self,
        *,
        user_id: int,
        osu_path_md5: str,
        adapters_md5: str,
        uninstall_md5: str,
        disk_signature_md5: str,
    ) -> None:
        await self.client_hashes.create(
            userid=user_id,
            osupath=osu_path_md5,
            adapters=adapters_md5,
            uninstall_id=uninstall_md5,
            disk_serial=disk_signature_md5,
        )

    async def fetch_hardware_matches(
        self,
        *,
        user_id: int,
        running_under_wine: bool,
        adapters_md5: str,
        uninstall_md5: str,
        disk_signature_md5: str | None,
    ) -> list[ClientHashWithPlayer]:
        return await self.client_hashes.fetch_any_hardware_matches_for_user(
            userid=user_id,
            running_under_wine=running_under_wine,
            adapters=adapters_md5,
            uninstall_id=uninstall_md5,
            disk_serial=disk_signature_md5,
        )

    async def update_country(
        self,
        *,
        user_id: int,
        country: str,
    ) -> None:
        await self.users.partial_update(id=user_id, country=country)

    async def fetch_unread_mail(self, player_id: int) -> list[MailWithUsernames]:
        return await self.mail.fetch_all_mail_to_user(user_id=player_id, read=False)


def has_restricted_hardware_match(matches: list[ClientHashWithPlayer]) -> bool:
    return not all([match["priv"] & Privileges.UNRESTRICTED for match in matches])
