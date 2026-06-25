from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from app.constants.clientflags import LastFMFlags
from app.objects.player import Player


class ClientIntegrityResult(StrEnum):
    EMPTY = "empty"
    STOP_SENDING = "stop_sending"


@dataclass(frozen=True)
class ClientIntegrityService:
    restriction_admin: Player
    restriction_roll: Callable[[int], int]
    send_notification: Callable[[Player, str], None]

    async def handle_lastfm_flags(
        self,
        *,
        player: Player,
        beatmap_id_or_hidden_flag: str,
    ) -> ClientIntegrityResult:
        if not beatmap_id_or_hidden_flag or beatmap_id_or_hidden_flag[0] != "a":
            # not anticheat related, tell the
            # client not to send any more for now.
            return ClientIntegrityResult.STOP_SENDING

        flags = LastFMFlags(int(beatmap_id_or_hidden_flag[1:]))

        if flags & (LastFMFlags.HQ_ASSEMBLY | LastFMFlags.HQ_FILE):
            # Player is currently running hq!osu; could possibly
            # be a separate client, buuuut prooobably not lol.
            await self._restrict_and_refresh_client(
                player,
                reason=f"hq!osu running ({flags})",
            )
            return ClientIntegrityResult.STOP_SENDING

        if flags & LastFMFlags.REGISTRY_EDITS:
            # Player has registry edits left from
            # hq!osu's multiaccounting tool. This
            # does not necessarily mean they are
            # using it now, but they have in the past.
            if self.restriction_roll(32) == 0:
                # Random chance (1/32) for a ban.
                await self._restrict_and_refresh_client(
                    player,
                    reason="hq!osu relife 1/32",
                )
                return ClientIntegrityResult.STOP_SENDING

            self.send_notification(
                player,
                "\n".join(
                    [
                        "Hey!",
                        "It appears you have hq!osu's multiaccounting tool (relife) enabled.",
                        "This tool leaves a change in your registry that the osu! client can detect.",
                        "Please re-install relife and disable the program to avoid any restrictions.",
                    ],
                ),
            )
            player.logout()
            return ClientIntegrityResult.STOP_SENDING

        """ These checks only worked for ~5 hours from release. rumoi's quick!
        if flags & (
            LastFMFlags.SDL2_LIBRARY
            | LastFMFlags.OPENSSL_LIBRARY
            | LastFMFlags.AQN_MENU_SAMPLE
        ):
            # AQN has been detected in the client, either
            # through the 'libeay32.dll' library being found
            # onboard, or from the menu sound being played in
            # the AQN menu while being in an inappropriate menu
            # for the context of the sound effect.
            pass
        """

        return ClientIntegrityResult.EMPTY

    async def _restrict_and_refresh_client(
        self,
        player: Player,
        *,
        reason: str,
    ) -> None:
        await player.restrict(admin=self.restriction_admin, reason=reason)

        # refresh their client state
        if player.is_online:
            player.logout()
