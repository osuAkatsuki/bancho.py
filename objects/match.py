# -*- coding: utf-8 -*-

from typing import Final, Optional, Union, Tuple
from dataclasses import dataclass
from enum import IntEnum, unique
from objects import glob
from objects.channel import Channel

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
    open:       Final[int] = 1
    locked:     Final[int] = 2
    not_ready:  Final[int] = 4
    ready:      Final[int] = 8
    no_map:     Final[int] = 16
    playing:    Final[int] = 32
    complete:   Final[int] = 64
    has_player: Final[int] = not_ready | ready | no_map | playing | complete
    quit:       Final[int] = 128

@unique
class Teams(IntEnum):
    neutral: Final[int] = 0
    blue:    Final[int] = 1
    red:     Final[int] = 2

@unique
class MatchTypes(IntEnum):
    standard:  Final[int] = 0
    powerplay: Final[int] = 1 # Literally no idea what this is for

@unique
class MatchScoringTypes(IntEnum):
    score:    Final[int] = 0
    accuracy: Final[int] = 1
    combo:    Final[int] = 2
    scorev2:  Final[int] = 3

@unique
class MatchTeamTypes(IntEnum):
    head_to_head: Final[int] = 0
    tag_coop:     Final[int] = 1
    team_vs:      Final[int] = 2
    tag_team_vs:  Final[int] = 3

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
    __slots__ = ('player', 'status', 'team', 'mods', 'loaded', 'skipped')

    def __init__(self) -> None:
        self.player = None
        self.status = SlotStatus.open
        self.team = Teams.neutral
        self.mods = 0
        self.loaded = False
        self.skipped = False

    def empty(self) -> None:
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

    map_id: :class:`int`
        The id of the currently selected map.

    map_name: :class:`str`
        The name of the currently selected map.

    map_md5: :class:`str`
        The md5 of the currently selected map.

    mods: :class:`int`
        The match's currently selected mods.

    freemods: :class:`bool`
        Whether the match is in freemods mode.

    game_mode: :class:`int`
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
        'map_id', 'map_name', 'map_md5',
        'mods', 'freemods', 'game_mode',
        'chat', 'slots',
        'type', 'team_type', 'match_scoring',
        'in_progress', 'seed'
    )

    def __init__(self) -> None:
        self.id = 0
        self.name = ''
        self.passwd = ''
        self.host = None

        self.map_id = 0
        self.map_name = ''
        self.map_md5 = ''

        self.mods = 0
        self.freemods = False
        self.game_mode = 0

        self.chat: Optional[Channel] = None
        self.slots = [Slot() for _ in range(16)]

        self.type = MatchTypes.standard
        self.team_type = MatchTeamTypes.head_to_head
        self.match_scoring = MatchScoringTypes.score

        self.in_progress = False
        self.seed = 0

    @property
    def url(self) -> str:
        return f'osump://{self.id}/{self.passwd}'

    @property
    def embed(self) -> str:
        return f'[{self.url} {self.name}]'

    def __contains__(self, p) -> bool:
        return p in {s.player for s in self.slots}

    def __getitem__(self, key: Union[int, slice]) -> Slot:
        return self.slots[key]

    #def __setitem__(self, key: Union[int, slice],
    #                value: Slot) -> None:
    #    self.slots[key] = value

    def __repr__(self) -> str:
        return f'<id: {self.id} | name: {self.name}>'

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
        self.map_id = m.map_id
        self.map_md5 = m.map_md5
        self.map_name = m.map_name
        self.freemods = m.freemods
        self.game_mode = m.game_mode
        self.team_type = m.team_type
        self.match_scoring = m.match_scoring
        self.mods = m.mods
        self.name = m.name

    def enqueue(self, data: bytes, lobby: bool = True,
                immune: Tuple[int, ...] = ()) -> None:
        if self.chat:
            self.chat.enqueue(data, immune)
        else:
            for p in (s.player for s in self.slots if s.player):
                if p.id not in immune:
                    p.enqueue(data)

        if lobby:
            glob.channels.get('#lobby').enqueue(data)
