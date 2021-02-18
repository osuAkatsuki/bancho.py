# -*- coding: utf-8 -*-

import asyncio
import lzma
import time
from pathlib import Path
from typing import TYPE_CHECKING

from cmyui.osu import ReplayFrame
from cmyui.discord import Webhook
from cmyui.discord import Embed
from cmyui import log, Ansi

import packets
from constants.gamemodes import GameMode
from constants.privileges import Privileges
from objects import glob
from utils.misc import get_press_times

if TYPE_CHECKING:
    from objects.score import Score

__all__ = ('donor_expiry', 'disconnect_ghosts',
           'replay_detections', 'reroll_bot_status')

async def donor_expiry() -> None:
    """Add new donation ranks & enqueue tasks to remove current ones."""
    # TODO: this system can get quite a bit better; rather than just
    # removing, it should rather update with the new perks (potentially
    # a different tier, enqueued after their current perks).

    async def rm_donor(userid: int, when: int):
        if (delta := when - time.time()) >= 0:
            await asyncio.sleep(delta)

        p = await glob.players.get_ensure(id=userid)

        # TODO: perhaps make a `revoke_donor` method?
        await p.remove_privs(Privileges.Donator)
        await glob.db.execute(
            'UPDATE users '
            'SET donor_end = 0 '
            'WHERE id = %s',
            [p.id]
        )

        if p.online:
            p.enqueue(packets.notification('Your supporter status has expired.'))

        log(f"{p}'s supporter status has expired.", Ansi.LMAGENTA)

    # enqueue rm_donor for any supporter
    # expiring in the next 30 days.
    query = (
        'SELECT id, donor_end FROM users '
        'WHERE donor_end < DATE_ADD(NOW(), INTERVAL 30 DAY) '
        'AND priv & 48' # 48 = Supporter | Premium
    )

    loop = asyncio.get_running_loop()

    async for donation in glob.db.iterall(query, _dict=False):
        loop.create_task(rm_donor(*donation))

PING_TIMEOUT = 300000 // 1000 # defined by osu!
async def disconnect_ghosts() -> None:
    """Actively disconnect users above the
       disconnection time threshold on the osu! server."""
    while True:
        ctime = time.time()

        async with glob.players._lock:
            for p in glob.players:
                if ctime - p.last_recv_time > PING_TIMEOUT:
                    await p.logout()

        # run this indefinitely
        await asyncio.sleep(PING_TIMEOUT // 3)

# This function is currently pretty tiny and useless, but
# will just continue to expand as more ideas come to mind.
async def analyze_score(score: 'Score') -> None:
    """Analyze a single score."""
    player = score.player

    # open & parse replay files frames
    replay_file = REPLAYS_PATH / f'{score.id}.osr'
    data = lzma.decompress(replay_file.read_bytes())

    frames: list[ReplayFrame] = []

    # ignore seed & blank line at end
    for action in data.decode().split(',')[:-2]:
        if frame := ReplayFrame.from_str(action):
            frames.append(frame)

    if score.mode.as_vanilla == GameMode.vn_taiko:
        # calculate their average press times.
        # NOTE: this does not currently take hit object
        # type into account, making it completely unviable
        # for any gamemode with holds. it's still relatively
        # reliable for taiko though :D.

        press_times = get_press_times(frames)
        config = glob.config.surveillance['hitobj_low_presstimes']

        cond = lambda pt: (sum(pt) / len(pt) < config['value']
                           and len(pt) > config['min_presses'])

        if any(map(cond, press_times.values())):
            # at least one of the keys is under the
            # minimum, log this occurence to Discord.
            webhook_url = glob.config.webhooks['surveillance']
            webhook = Webhook(url=webhook_url)

            embed = Embed(
                title = f'[{score.mode!r}] Abnormally low presstimes detected'
            )

            embed.set_author(
                url = player.url,
                name = player.name,
                icon_url = player.avatar_url
            )

            # TODO: think of a way to organize a thumbnail into config?
            thumb_url = 'https://akatsuki.pw/static/logos/logo.png'
            embed.set_thumbnail(url=thumb_url)

            for key, pt in press_times.items():
                embed.add_field(
                    name = f'Key: {key.name}',
                    value = f'{sum(pt) / len(pt):.2f}ms' if pt else 'N/A',
                    inline = True
                )

            webhook.add_embed(embed)
            await webhook.post(glob.http)

REPLAYS_PATH = Path.cwd() / '.data/osr'
async def replay_detections() -> None:
    """Actively run a background thread throughout gulag's
       lifespan; it will pull replays determined as sketch
       from a queue indefinitely."""
    glob.sketchy_queue = asyncio.Queue() # cursed type hint fix
    queue: asyncio.Queue['Score'] = glob.sketchy_queue

    loop = asyncio.get_running_loop()

    while score := await queue.get():
        loop.create_task(analyze_score(score))

async def reroll_bot_status(interval: int) -> None:
    """Reroll the bot's status, every `interval`."""
    while True:
        await asyncio.sleep(interval)
        packets.botStats.cache_clear()
