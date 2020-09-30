# -*- coding: utf-8 -*-

from typing import Optional, Union, Tuple
from dataclasses import dataclass
from enum import IntEnum, unique
from objects import glob
from objects.channel import Channel
from objects.beatmap import Beatmap

__all__ = (
    'SlotStatus',
    'Teams',
    'MatchTypes',
    'MatchScoringTypes',
    'MatchTeamTypes',
    'ScoreFrame',
    'Slot',
    'Match'
)

@unique
class SlotStatus(IntEnum):
    open       = 1
    locked     = 2
    not_ready  = 4
    ready      = 8
    no_map     = 16
    playing    = 32
    complete   = 64
    has_player = not_ready | ready | no_map | playing | complete
    quit       = 128

@unique
class Teams(IntEnum):
    neutral = 0
    blue    = 1
    red     = 2

@unique
class MatchTypes(IntEnum):
    standard  = 0
    powerplay = 1 # literally no idea what this is for

@unique
class MatchScoringTypes(IntEnum):
    score    = 0
    accuracy = 1
    combo    = 2
    scorev2  = 3

@unique
class MatchTeamTypes(IntEnum):
    head_to_head = 0
    tag_coop     = 1
    team_vs      = 2
    tag_team_vs  = 3

@dataclass
class ScoreFrame:
    time: int
    id: int
    num300: int
    num100: int
    num50: int
    num_geki: int
    num_katu: int
    num_miss: int
    total_score: int
    current_combo: int
    max_combo: int
    perfect: bool
    current_hp: int
    tag_byte: int

    # scorev2 only
    score_v2: Optional[bool] = None
    combo_portion: Optional[int] = None
    bonus_portion: Optional[int] = None

class Slot:
    """A class to represent a single slot in an osu! multiplayer match.

    Attributes
    -----------
    player: Optional[:class:`Player`]
        A player obj representing the player in the slot, if available.

    status: :class:`SlotStatus`
        An obj representing the slot's current status.

    team: :class:`Teams`
        An obj representing the slot's current team.

    mods: :class:`int`
        The slot's currently selected mods.

    loaded: :class:`bool`
        Whether the player is loaded into the current map.

    skipped: :class:`bool`
        Whether the player has decided to skip the current map intro.
    """
    __slots__ = ('player', 'status', 'team',
                 'mods', 'loaded', 'skipped')

    def __init__(self) -> None:
        self.player = None
        self.status = SlotStatus.open
        self.team = Teams.neutral
        self.mods = 0
        self.loaded = False
        self.skipped = False

    def empty(self) -> bool:
        return self.player is None

    def copy(self, s) -> None:
        self.player = s.player
        self.status = s.status
        self.team = s.team
        self.mods = s.mods

    def reset(self) -> None:
        self.player = None
        self.status = SlotStatus.open
        self.team = Teams.neutral
        self.mods = 0
        self.loaded = False
        self.skipped = False

class Match:
    """A class to represent an osu! multiplayer match.

    Attributes
    -----------
    id: :class:`int`
        The match's unique ID.

    name: :class:`str`
        The match's name.

    passwd: :class:`str`
        The match's password.

    host: :class:`Player`
        A player obj of the match's host.

    bmap: Optional[:class:`Beatmap`]
        A beatmap obj representing the osu map.

    mods: :class:`int`
        The match's currently selected mods.

    freemods: :class:`bool`
        Whether the match is in freemods mode.

    mode: :class:`int`
        The match's currently selected gamemode.

    chat: :class:`Channel`
        A channel obj of the match's chat.

    slots: List[:class:`Slot`]
        A list of 16 slots representing the match's slots.

    type: :class:`MatchTypes`
        The match's currently selected match type.

    team_type: :class:`MatchTeamTypes`
        The match's currently selected team type.

    match_scoring: :class:`MatchScoringTypes`
        The match's currently selected match scoring type.

    in_progress: :class:`bool`
        Whether the match is currently in progress.

    seed: :class:`int`
        The match's randomly generated seed.
        XXX: this is used for osu!mania's random mod!
    """
    __slots__ = (
        'id', 'name', 'passwd', 'host',
        'bmap',
        'mods', 'freemods', 'mode',
        'chat', 'slots',
        'type', 'team_type', 'match_scoring',
        'in_progress', 'seed'
    )

    def __init__(self) -> None:
        self.id = 0
        self.name = ''
        self.passwd = '' # TODO: filter from lobby
        self.host = None

        self.bmap: Optional[Beatmap] = None

        self.mods = 0
        self.freemods = False
        self.mode = 0

        self.chat: Optional[Channel] = None
        self.slots = [Slot() for _ in range(16)]

        self.type = MatchTypes.standard
        self.team_type = MatchTeamTypes.head_to_head
        self.match_scoring = MatchScoringTypes.score

        self.in_progress = False
        self.seed = 0

    @property
    def url(self) -> str:
        """The match's invitation url."""
        return f'osump://{self.id}/{self.passwd}'

    @property
    def embed(self) -> str:
        """An osu! chat embed for the match."""
        return f'[{self.url} {self.name}]'

    def __contains__(self, p) -> bool:
        return p in {s.player for s in self.slots}

    def __getitem__(self, key: Union[int, slice]) -> Slot:
        return self.slots[key]

    def __repr__(self) -> str:
        return f'<{self.name} ({self.id})>'

    def get_slot(self, p) -> Optional[Slot]:
        # Get the slot containing a given player.
        for s in self.slots:
            if p == s.player:
                return s

    def get_slot_id(self, p) -> Optional[int]:
        # Get the slot index containing a given player.
        for idx, s in enumerate(self.slots):
            if p == s.player:
                return idx

    def get_free(self) -> Optional[Slot]:
        # Get the first free slot index.
        for idx, s in enumerate(self.slots):
            if s.status == SlotStatus.open:
                return idx

    def copy(self, m) -> None:
        """Fully copy the data of another match obj."""

        self.bmap = m.bmap
        self.freemods = m.freemods
        self.mode = m.mode
        self.team_type = m.team_type
        self.match_scoring = m.match_scoring
        self.mods = m.mods
        self.name = m.name

    def enqueue(self, data: bytes, lobby: bool = True,
                immune: Tuple[int, ...] = ()) -> None:
        """Add data to be sent to all clients in the match."""

        if self.chat:
            self.chat.enqueue(data, immune)
        else:
            for p in (s.player for s in self.slots if s.player):
                if p.id not in immune:
                    p.enqueue(data)

        if lobby and (lchan := glob.channels['#lobby']):
            lchan.enqueue(data)
