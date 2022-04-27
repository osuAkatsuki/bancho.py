from __future__ import annotations

from ipaddress import IPv4Address
from ipaddress import IPv6Address
from typing import Literal
from typing import Union

IPAddress = Union[IPv4Address, IPv6Address]

# some types used within the osu! client

OsuClientModes = Literal[
    "Menu",
    "Edit",
    "Play",
    "Exit",
    "SelectEdit",
    "SelectPlay",
    "SelectDrawings",
    "Rank",
    "Update",
    "Busy",
    "Unknown",
    "Lobby",
    "MatchSetup",
    "SelectMulti",
    "RankingVs",
    "OnlineSelection",
    "OptionsOffsetWizard",
    "RankingTagCoop",
    "RankingTeam",
    "BeatmapImport",
    "PackageUpdater",
    "Benchmark",
    "Tourney",
    "Charts",
]

OsuClientGameModes = Literal[
    "Osu",
    "Taiko",
    "CatchTheBeat",
    "OsuMania",
]
