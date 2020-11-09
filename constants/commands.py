# -*- coding: utf-8 -*-

import asyncio
from utils.recalculator import PPCalculator
from typing import Sequence, Optional, Union, Callable
import time
import cmyui
import random
from collections import defaultdict

import packets

from constants.privileges import Privileges
from constants.mods import Mods
from constants import regexes

from objects import glob
from objects.player import Player
from objects.channel import Channel
from objects.beatmap import Beatmap, RankedStatus
from objects.match import (Match, MatchScoringTypes,
                           MatchTeamTypes, SlotStatus)

Messageable = Union[Channel, Player]
CommandResponse = dict[str, str]

# not sure if this should be in glob or not,
# trying to think of some use cases lol..
glob.commands = []

def command(priv: Privileges, public: bool,
            trigger: Optional[str] = None) -> Callable:
    def register_callback(callback: Callable):
        glob.commands.append({
            'trigger': trigger or f'!{callback.__name__}',
            'callback': callback,
            'priv': priv,
            'public': public,
            'doc': callback.__doc__
        })

        return callback
    return register_callback

""" User commands
# The commands below are not considered dangerous,
# and are granted to any unbanned players.
"""

@command(trigger='!help', priv=Privileges.Normal, public=False)
async def _help(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Show information of all documented commands `p` can use."""
    return '\n'.join('{trigger}: {doc}'.format(**cmd)
                     for cmd in glob.commands if cmd['doc']
                     if p.priv & cmd['priv'])

@command(priv=Privileges.Normal, public=True)
async def roll(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Roll an n-sided die where n is the number you write (100 if empty)."""
    if msg and msg[0].isdecimal():
        max_roll = min(int(msg[0]), 0x7fff)
    else:
        max_roll = 100

    points = random.randrange(0, max_roll)
    return f'{p.name} rolls {points} points!'

@command(priv=Privileges.Normal, public=True)
async def bloodcat(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Return a bloodcat link of the user's current map (situation dependant)."""
    bmap = None

    if p.match and p.match.bmap:
        # return the match beatmap
        bmap = p.match.bmap
    # TODO: spectator?
    elif p.last_np:
        bmap = p.last_np
    else:
        return 'No map found!'

    return '[https://bloodcat.com/d/{} {}]'.format(bmap.set_id, bmap.full)

@command(priv=Privileges.Normal, public=True)
async def last(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Show information about your most recent score."""
    if not (s := p.recent_score):
        return 'No scores found :o'

    return (f'[{s.mode!r}] {s.bmap.embed} {s.mods!r} {s.acc:.2f}% | '
            f'{s.pp:.2f}pp #{s.rank}')

@command(priv=Privileges.Normal, public=False)
async def mapsearch(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Search map titles with user input as a wildcard."""
    if not msg:
        return 'Invalid syntax: !mapsearch <title>'

    if not (res := await glob.db.fetchall(
        'SELECT id, set_id, artist, title, version '
        'FROM maps WHERE title LIKE %s LIMIT 50',
        [f'%{" ".join(msg)}%']
    )): return 'No matches found :('

    mirror = glob.config.mirror

    return '\n'.join(
        '[https://osu.ppy.sh/b/{id} {artist} - {title} [{version}]] '
        '([{mirror}/d/{set_id} download])'.format(**row, mirror=mirror)
        for row in res
    ) + f'\nMaps: {len(res)}'

# TODO: refactor with acc and more stuff
@command(trigger='!with', priv=Privileges.Normal, public=False)
async def _with(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Specify custom accuracy & mod combinations with `/np`."""
    if isinstance(c, Channel) or c.id != 1:
        return 'This command can only be used in DM with Aika.'

    if not p.last_np:
        return 'Please /np a map first!'

    # +?<mods> <acc>%?
    if 1 < len(msg) > 2:
        return 'Invalid syntax: !with <mods/acc> ...'

    mods = acc = None

    for param in (p.strip('+%') for p in msg):
        if cmyui._isdecimal(param, _float=True):
            if not 0 <= (acc := float(param)) <= 100:
                return 'Invalid accuracy.'

        elif ~len(param) & 1: # len(param) % 2 == 0
            mods = Mods.from_str(param)
        else:
            return 'Invalid syntax: !with <mods/acc> ...'

    _msg = [p.last_np.embed]
    if not mods:
        mods = Mods.NOMOD

    _msg.append(repr(mods))

    if acc:
        # custom accuracy specified, calculate it on the fly.
        ppcalc = await PPCalculator.from_id(p.last_np.id, acc=acc, mods=mods)
        if not ppcalc:
            return 'Could not retrieve map file.'

        pp, _ = await ppcalc.perform() # don't need sr
        pp_values = [(acc, pp)]
    else:
        # general accuracy values requested.
        if mods not in p.last_np.pp_cache:
            # cache
            await p.last_np.cache_pp(mods)

        pp_values = zip(
            (90, 95, 98, 99, 100),
            p.last_np.pp_cache[mods]
        )

    pp_msg = ' | '.join(f'{acc:.2f}%: {pp:.2f}pp'
                        for acc, pp in pp_values)
    return f"{' '.join(_msg)}: {pp_msg}"

""" Nominators commands
# The commands below allow users to
# manage  the server's state of beatmaps.
"""

status_to_id = lambda s: {
    'unrank': 0,
    'rank': 2,
    'love': 5
}[s]
@command(trigger='!map', priv=Privileges.Nominator, public=True)
async def _map(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Changes the ranked status of the most recently /np'ed map."""
    if len(msg) != 2 or msg[0] not in ('rank', 'unrank', 'love') \
                     or msg[1] not in ('set', 'map'):
        return 'Invalid syntax: !map <rank/unrank/love> <map/set>'

    if not p.last_np:
        return 'You must /np a map first!'

    new_status = status_to_id(msg[0])

    # update sql & cache based on scope
    # XXX: not sure if getting md5s from sql
    # for updating cache would be faster?
    # surely this will not scale as well..

    if msg[1] == 'set':
        # update whole set
        await glob.db.execute(
            'UPDATE maps SET status = %s, '
            'frozen = 1 WHERE set_id = %s',
            [new_status, p.last_np.set_id]
        )

        for cached in glob.cache['beatmap'].values():
            # not going to bother checking timeout
            if cached['map'].set_id == p.last_np.set_id:
                cached['map'].status = RankedStatus(new_status)

    else:
        # update only map
        await glob.db.execute(
            'UPDATE maps SET status = %s, '
            'frozen = 1 WHERE id = %s',
            [new_status, p.last_np.id]
        )

        for cached in glob.cache['beatmap'].values():
            # not going to bother checking timeout
            if cached['map'].id == p.last_np.id:
                cached['map'].status = RankedStatus(new_status)
                break

    return 'Map updated!'

""" Mod commands
# The commands below are somewhat dangerous,
# and are generally for managing players.
"""

@command(priv=Privileges.Mod, public=False)
async def notes(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Retrieve the logs of a specified player by name."""
    if len(msg) != 2 or not msg[1].isdecimal():
        return 'Invalid syntax: !notes <name> <days_back>'

    if not (t := await glob.players.get_by_name(msg[0], sql=True)):
        return f'"{msg[0]}" not found.'

    if (days := int(msg[1])) > 365:
        return 'Please contact a developer to fetch >365 day old information.'

    res = await glob.db.fetchall(
        'SELECT `msg`, `time` '
        'FROM `logs` WHERE `to` = %s '
        'AND UNIX_TIMESTAMP(`time`) >= UNIX_TIMESTAMP(NOW()) - %s '
        'ORDER BY `time` ASC',
        [t.id, days * 86400]
    )

    return '\n'.join(
        '[{time}] {msg}'.format(**row)
        for row in res
    )

@command(priv=Privileges.Mod, public=False)
async def addnote(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Add a note to a specified player by name."""
    if len(msg) < 2:
        return 'Invalid syntax: !addnote <name> <note ...>'

    if not (t := await glob.players.get_by_name(msg[0], sql=True)):
        return f'"{msg[0]}" not found.'

    log_msg = f'{p} added note: {" ".join(msg[1:])}'

    await glob.db.execute(
        'INSERT INTO logs (`from`, `to`, `msg`, `time`) '
        'VALUES (%s, %s, %s, NOW())',
        [p.id, t.id, log_msg]
    )

    return f'Added note to {p}.'

@command(priv=Privileges.Mod, public=False)
async def silence(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Silence `p` with a specified duration & reason."""
    if len(msg) < 3:
        return 'Invalid syntax: !silence <name> <duration> <reason>'

    if not (t := await glob.players.get_by_name(msg[0], sql=True)):
        return f'"{msg[0]}" not found.'

    if t.priv & Privileges.Staff and not p.priv & Privileges.Dangerous:
        return 'Only developers can manage staff members.'

    if not (rgx := regexes.silence_duration.match(msg[1])):
        return 'Invalid syntax: !silence <name> <duration> <reason>'

    multiplier = {
        's': 1, 'm': 60, 'h': 3600,
        'd': 86400, 'w': 604800
    }[rgx['scale']]

    duration = int(rgx['duration']) * multiplier
    reason = ' '.join(msg[2:])

    await t.silence(p, duration, reason)
    return f'{t} was silenced.'

@command(priv=Privileges.Mod, public=False)
async def unsilence(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Unsilence `p`."""
    if len(msg) != 1:
        return 'Invalid syntax: !unsilence <name>'

    if not (t := await glob.players.get_by_name(msg[0], sql=True)):
        return f'"{msg[0]}" not found.'

    if not t.silenced:
        return f'{t} is not silenced.'

    if t.priv & Privileges.Staff and not p.priv & Privileges.Dangerous:
        return 'Only developers can manage staff members.'

    await t.unsilence(p)
    return f'{t} was unsilenced.'

""" Admin commands
# The commands below are relatively dangerous,
# and are generally for managing players.
"""

@command(priv=Privileges.Admin, public=False)
async def ban(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Ban a player's account, with a reason."""
    if len(msg) < 2:
        return 'Invalid syntax: !ban <name> (reason)'

    # find any user matching (including offline).
    if not (t := await glob.players.get_by_name(msg[0], sql=True)):
        return f'"{msg[0]}" not found.'

    if t.priv & Privileges.Staff and not p.priv & Privileges.Dangerous:
        return 'Only developers can manage staff members.'

    reason = ' '.join(msg[1:])

    await t.ban(p, reason)
    return f'{t} was banned.'

@command(priv=Privileges.Admin, public=False)
async def unban(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Unban a player's account, with a reason."""
    if (len_msg := len(msg)) < 2:
        return 'Invalid syntax: !ban <name> (reason)'

    # find any user matching (including offline).
    if not (t := await glob.players.get_by_name(msg[0], sql=True)):
        return f'"{msg[0]}" not found.'

    if t.priv & Privileges.Staff and not p.priv & Privileges.Dangerous:
        return 'Only developers can manage staff members.'

    reason = ' '.join(msg[2:]) if len_msg > 2 else None

    await t.unban(p, reason)
    return f'{t} was unbanned.'

@command(priv=Privileges.Admin, public=False)
async def alert(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Send a notification to all players."""
    if len(msg) < 1:
        return 'Invalid syntax: !alert <msg>'

    glob.players.enqueue(packets.notification(' '.join(msg)))
    return 'Alert sent.'

@command(trigger='!alertu', priv=Privileges.Admin, public=False)
async def alert_user(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Send a notification to a specific player by name."""
    if len(msg) < 2:
        return 'Invalid syntax: !alertu <name> <msg>'

    if not (t := await glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    t.enqueue(packets.notification(' '.join(msg[1:])))
    return 'Alert sent.'

""" Developer commands
# The commands below are either dangerous or
# simply not useful for any other roles.
"""

@command(priv=Privileges.Dangerous, public=True)
async def recalc(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Performs a full PP recalc on a specified map, or all maps."""
    if len(msg) != 1 or msg[0] not in ('map', 'all'):
        return 'Invalid syntax: !recalc <map/all>'

    score_counts = [] # keep track of # of scores recalced

    if msg[0] == 'map':
        # recalculate all scores on their last /np'ed map.
        if not p.last_np:
            return 'You must /np a map first!'

        ppcalc = await PPCalculator.from_id(p.last_np.id)
        if not ppcalc:
            return 'Could not retrieve map file.'

        await c.send(glob.bot, f'Performing full recalc on {p.last_np.embed}.')

        for table in ('scores_vn', 'scores_rx', 'scores_ap'):
            # fetch all scores from the table on this map
            scores = await glob.db.fetchall(
                'SELECT id, acc, mods, max_combo, '
                'n300, n100, n50, nmiss, ngeki, nkatu '
                f'FROM {table} WHERE map_md5 = %s '
                'AND status = 2 AND mode = 0',
                [p.last_np.md5]
            )

            score_counts.append(len(scores))

            if not scores:
                continue

            for score in scores:
                ppcalc.mods = Mods(score['mods'])
                ppcalc.combo = score['max_combo']
                ppcalc.nmiss = score['nmiss']
                ppcalc.acc = score['acc']

                pp, _ = await ppcalc.perform() # sr not needed

                await glob.db.execute(
                    f'UPDATE {table} '
                    'SET pp = %s '
                    'WHERE id = %s',
                    [pp, score['id']]
                )

    else:
        # recalculate all scores on every map
        if not p.priv & Privileges.Dangerous:
            return 'This command is limited to developers.'

        return 'TODO'

    recap = '{0} vn | {1} rx | {2} ap'.format(*score_counts)
    return f'Recalculated {sum(score_counts)} ({recap}) scores.'

@command(trigger='!switchserv', priv=Privileges.Dangerous, public=False)
async def switch_server(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Switch servers to a specified ip address."""
    if len(msg) != 1:
        return 'Invalid syntax: !switch <endpoint>'

    p.enqueue(packets.switchTournamentServer(msg[0]))
    return 'Have a nice journey..'

# rest in peace rtx - oct 2020 :candle:
#@command(priv=Privileges.Dangerous, public=False)
#async def rtx(p: Player, c: Messageable, msg: Sequence[str]) -> str:
#    """Send an RTX packet with a message to a user."""
#    if len(msg) != 2:
#        return 'Invalid syntax: !rtx <name> <msg>'
#
#    if not (t := await glob.players.get_by_name(msg[0])):
#        return 'Could not find a user by that name.'
#
#    t.enqueue(packets.RTX(msg[1]))
#    return 'pong'

# XXX: not very useful, mostly just for testing/fun.
@command(trigger='!spack', priv=Privileges.Dangerous, public=False)
async def send_empty_packet(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Send a specific (empty) packet by id to a player."""
    if len(msg) < 2 or not msg[-1].isdecimal():
        return 'Invalid syntax: !spack <name> <packetid>'

    if not (t := await glob.players.get_by_name(' '.join(msg[:-1]))):
        return 'Could not find a user by that name.'

    packet = packets.BanchoPacket(int(msg[-1]))
    t.enqueue(packets.write(packet))
    return f'Wrote {packet!r} to {t}.'

@command(priv=Privileges.Dangerous, public=False)
async def debug(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Toggle the console's debug setting."""
    glob.config.debug = not glob.config.debug
    return f"Toggled {'on' if glob.config.debug else 'off'}."

str_to_priv = lambda p: defaultdict(lambda: None, {
    'normal': Privileges.Normal,
    'verified': Privileges.Verfied,
    'whitelisted': Privileges.Whitelisted,
    'supporter': Privileges.Supporter,
    'premium': Privileges.Premium,
    'tournament': Privileges.Tournament,
    'nominator': Privileges.Nominator,
    'mod': Privileges.Mod,
    'admin': Privileges.Admin,
    'dangerous': Privileges.Dangerous
})[p]
@command(priv=Privileges.Dangerous, public=False)
async def setpriv(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Set privileges for a player (by name)."""
    if len(msg) < 2:
        return 'Invalid syntax: !setpriv <name> <role1 | role2 | ...>'

    # a mess that gets each unique privilege out of msg.
    # TODO: rewrite to be at least a bit more readable..
    priv = [str_to_priv(i) for i in set(''.join(msg[1:]).replace(' ', '').lower().split('|'))]
    if any(x is None for x in priv):
        return 'Invalid privileges.'

    if not (t := await glob.players.get_by_name(msg[0], sql=True)):
        return 'Could not find user.'

    await glob.db.execute('UPDATE users SET priv = %s WHERE id = %s',
                    [newpriv := sum(priv), t.id])

    t.priv = Privileges(newpriv)
    return 'Success.'

# temp command, to illustrate how menu options will work
@command(trigger='!men', priv=Privileges.Dangerous, public=False)
async def menu_preview(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    async def callback():
        # this is called when the menu item is clicked
        p.enqueue(packets.notification('clicked!'))

    # add the option to their menu opts & send them a button
    opt_id = await p.add_to_menu(callback)
    return f'[osu://dl/{opt_id} option]'

# XXX: this actually comes in handy sometimes, i initially
# wrote it completely as a joke, but i might keep it in for
# devs.. Comes in handy when debugging to be able to run something
# like `!ev return await glob.players.get_by_name('cmyui').status.action`
# or for anything while debugging on-the-fly..
@command(priv=Privileges.Dangerous, public=False)
async def ex(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    # create the new coroutine definition as a string
    # with the lines from our message (split by '\n').
    lines = ' '.join(msg).split(r'\n')
    definition = '\n '.join(['async def __ex():'] + lines)

    try:
        # define, and run the coroutine
        exec(definition)
        ret = await locals()['__ex']() # type: ignore
    except Exception as e:
        # code was invalid, return
        # the error in the osu! chat.
        return str(e)

    return ret if ret else 'Success'

""" Multiplayer commands
# The commands below are specifically for
# multiplayer match management.
"""
glob.mp_commands = []

def mp_command(priv: Privileges, trigger: Optional[str] = None) -> Callable:
    def wrapper(f: Callable) -> Callable:
        glob.mp_commands.append({
            'trigger': trigger or f'{f.__name__.removeprefix("mp_")}',
            'callback': f,
            'priv': priv,
            'doc': f.__doc__
        })
        return f
    return wrapper

@mp_command(priv=Privileges.Normal)
async def mp_start(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Start a multiplayer match."""
    if (msg_len := len(msg)) > 1:
        return 'Invalid syntax: !mp start <force/seconds>'

    if msg_len == 1:
        if msg[0].isdecimal():
            # !mp start <seconds>
            duration = int(msg[0])
            if not 0 < duration <= 300:
                return 'Timer range is 1-300 seconds.'

            async def delayed_start(wait: int):
                await asyncio.sleep(wait)

                if p not in m:
                    # player left match since :monkaS:
                    return

                await m.chat.send(glob.bot, 'Good luck!')
                m.start()

            asyncio.create_task(delayed_start(duration))
            return f'Match will start in {duration} seconds.'
        elif msg[0] != 'force':
            return 'Invalid syntax: !mp start <force/seconds>'
        # !mp start force simply passes through
    else:
        # !mp start (no force or timer)
        if any(s.status == SlotStatus.not_ready for s in m.slots):
            return ('Not all players are ready '
                    '(use `!mp start force` to override).')

    m.start()
    return 'Good luck!'

@mp_command(priv=Privileges.Normal)
async def mp_abort(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Abort an in-progress multiplayer match."""
    if not m.in_progress:
        return 'Abort what?'

    m.unready_players(expected=SlotStatus.playing)

    m.in_progress = False
    m.enqueue(packets.matchAbort())
    m.enqueue_state()
    return 'Match aborted.'

@mp_command(priv=Privileges.Admin)
async def mp_force(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Force `p` into `m` by name."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp force <name>'

    if not (t := await glob.players.get_by_name(' '.join(msg))):
        return 'Could not find a user by that name.'

    await t.join_match(m)
    return 'Welcome.'

@mp_command(priv=Privileges.Normal)
async def mp_map(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Set `m`'s current map by id."""
    if len(msg) != 1 or not msg[0].isdecimal():
        return 'Invalid syntax: !mp map <beatmapid>'

    if not (bmap := await Beatmap.from_bid(int(msg[0]))):
        return 'Beatmap not found.'

    m.map_id = bmap.id
    m.map_md5 = bmap.md5
    m.map_name = bmap.full

    m.enqueue_state()
    return f'Map selected: {bmap.embed}.'

@mp_command(priv=Privileges.Normal)
async def mp_mods(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Set `m`'s mods, from string form."""
    if len(msg) != 1 or not ~len(msg[0]) & 1: # len(msg[0]) % 2 == 0
        return 'Invalid syntax: !mp mods <mods>'

    mods = Mods.from_str(msg[0])

    if m.freemods:
        if p.id == m.host.id:
            # allow host to set speed-changing mods.
            m.mods = mods & Mods.SPEED_CHANGING

        # set slot mods
        m.get_slot(p).mods = mods & ~Mods.SPEED_CHANGING
    else:
        # not freemods, set match mods.
        m.mods = mods

    m.enqueue_state()
    return 'Match mods updated.'

@mp_command(priv=Privileges.Normal)
async def mp_freemods(p: Player, m: Match, msg: Sequence[str]) -> str:
    if len(msg) != 1 or msg[0] not in ('on', 'off'):
        return 'Invalid syntax: !mp freemods <on/off>'

    if msg[0] == 'on':
        # central mods -> all players mods.
        m.freemods = True

        for s in m.slots:
            if s.status & SlotStatus.has_player:
                # the slot takes any non-speed
                # changing mods from the match.
                s.mods = m.mods & ~Mods.SPEED_CHANGING

        m.mods &= Mods.SPEED_CHANGING
    else:
        # host mods -> central mods.
        m.freemods = False
        host = m.get_host_slot() # should always exist
        # the match keeps any speed-changing mods,
        # and also takes any mods the host has enabled.
        m.mods &= Mods.SPEED_CHANGING
        m.mods |= host.mods

    m.enqueue_state()
    return 'Match freemod status updated.'

@mp_command(priv=Privileges.Normal)
async def mp_host(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Set `m`'s current host by id."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp host <name>'

    if not (t := await glob.players.get_by_name(' '.join(msg))):
        return 'Could not find a user by that name.'

    if m.host == t:
        return "They're already host, silly!"

    if t not in m:
        return 'Found no such player in the match.'

    m.host = t
    m.host.enqueue(packets.matchTransferHost())
    m.enqueue_state(lobby=False)
    return 'Match host updated.'

@mp_command(priv=Privileges.Normal)
async def mp_randpw(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Randomize `m`'s password."""
    m.passwd = cmyui.rstring(16)
    return 'Match password randomized.'

@mp_command(priv=Privileges.Normal)
async def mp_invite(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Invite a player to `m` by name."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp invite <name>'

    if not (t := await glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    if p == t:
        return "You can't invite yourself!"

    t.enqueue(packets.matchInvite(p, t.name))
    return f'Invited {t} to the match.'

@mp_command(priv=Privileges.Normal)
async def mp_addref(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Add a referee to `m` by name."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp addref <name>'

    if not (t := await glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    if t not in m:
        return 'User must be in the current match!'

    if t in m.refs:
        return f'{t} is already a match referee!'

    m._refs.add(t)
    return 'Match referees updated.'

@mp_command(priv=Privileges.Normal)
async def mp_rmref(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Remove a referee from `m` by name."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp addref <name>'

    if not (t := await glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    if t not in m.refs:
        return f'{t} is not a match referee!'

    if t == m.host:
        return 'The host is always a referee!'

    m._refs.remove(t)
    return 'Match referees updated.'

@mp_command(priv=Privileges.Normal)
async def mp_listref(p: Player, m: Match, msg: Sequence[str]) -> str:
    """List all referees from `m`."""
    return ', '.join(str(i) for i in m.refs) + '.'

@mp_command(priv=Privileges.Normal)
async def mp_lock(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Lock all unused slots in `m`."""
    for slot in m.slots:
        if slot.status == SlotStatus.open:
            slot.status = SlotStatus.locked

    m.enqueue_state()
    return 'All unused slots locked.'

@mp_command(priv=Privileges.Normal)
async def mp_unlock(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Unlock locked slots in `m`."""
    for slot in m.slots:
        if slot.status == SlotStatus.locked:
            slot.status = SlotStatus.open

    m.enqueue_state()
    return 'All locked slots unlocked.'

@mp_command(priv=Privileges.Normal)
async def mp_teams(p: Player, m: Match, msg: Sequence[str]) -> str:
    if len(msg) != 1 or msg[0] not in ('head-to-head', 'tag-coop',
                                       'team-vs', 'tag-team-vs'):
        return 'Invalid syntax: !mp teams <mode>'

    m.team_type = {
        'head-to-head': MatchTeamTypes.head_to_head,
        'tag-coop': MatchTeamTypes.tag_coop,
        'team-vs': MatchTeamTypes.team_vs,
        'tag-team-vs': MatchTeamTypes.tag_team_vs
    }[msg[0]]

    m.enqueue_state()
    return 'Match team type updated.'

@mp_command(priv=Privileges.Normal)
async def mp_condition(p: Player, m: Match, msg: Sequence[str]) -> str:
    if len(msg) != 1 or msg[0] not in ('score', 'accuracy',
                                       'combo', 'scorev2'):
        return 'Invalid syntax: !mp condition <mode>'

    m.match_scoring = {
        'score': MatchScoringTypes.score,
        'accuracy': MatchScoringTypes.accuracy,
        'combo': MatchScoringTypes.combo,
        'scorev2': MatchScoringTypes.scorev2
    }[msg[0]]

    m.enqueue_state(lobby=False)
    return 'Match win condition updated.'

@command(trigger='!mp', priv=Privileges.Normal, public=True)
async def multiplayer(p: Player, c: Messageable,
                      msg: Sequence[str]) -> str:
    """Multiplayer match main parent command."""

    # player not in a multiplayer match.
    if not (m := p.match):
        return 'This command can only be used from a multiplayer match.'

    # used outside of a multiplayer match.
    if not isinstance(c, Channel) or not c._name.startswith('#multi_'):
        return

    # missing privileges to use mp commands.
    if not (p in m.refs or p.priv & Privileges.Tournament):
        return

    # no subcommand specified, send back a list.
    if not msg:
        return '\n'.join('!mp {trigger}: {doc}'.format(**cmd)
                         for cmd in glob.mp_commands if cmd['doc']
                         if p.priv & cmd['priv'])

    # find a command with a matching
    # trigger & privilege level.

    for cmd in glob.mp_commands:
        if msg[0] == cmd['trigger'] and p.priv & cmd['priv']:
            # forward the params to the specific command.
            # XXX: here, rather than sending the channel
            # as the 2nd arg, we'll send the match obj.
            # this is used much more frequently, and we've
            # already asserted than p.match.chat == c anyways.
            return await cmd['callback'](p, m, msg[1:])
    else:
        # no commands triggered.
        return 'Invalid subcommand.'

async def process_commands(p: Player, t: Messageable,
                           msg: str) -> Optional[CommandResponse]:
    # response is either a CommandResponse if we hit a command,
    # or simply False if we don't have any command hits.
    st = time.time_ns()
    trigger, *args = msg.strip().split(' ')

    for cmd in glob.commands:
        if trigger == cmd['trigger'] and p.priv & cmd['priv']:
            # command found & we have privileges - run it.
            if (res := await cmd['callback'](p, t, args)):
                # returned a message for us to send back.
                # print elapsed time in milliseconds.
                time_taken = (time.time_ns() - st) / 1000000

                return {
                    'resp': f'{res} | Elapsed: {time_taken:.2f}ms',
                    'public': cmd['public']
                }

            return {'public': True}
