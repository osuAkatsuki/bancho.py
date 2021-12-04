import re

import app.settings
from app.objects import glob  # this will 100% become a problem

__all__ = ("OSU_VERSION", "USERNAME", "EMAIL", "NOW_PLAYING", "BEST_OF")

DOMAIN_ESCAPED = app.settings.DOMAIN.replace(".", r"\.")

OSU_VERSION = re.compile(
    r"^b(?P<ver>\d{8})(?:\.(?P<subver>\d))?"
    r"(?P<stream>beta|cuttingedge|dev|tourney)?$",
)

USERNAME = re.compile(r"^[\w \[\]-]{2,15}$")
EMAIL = re.compile(r"^[^@\s]{1,200}@[^@\s\.]{1,30}(?:\.[^@\.\s]{2,24})+$")

NOW_PLAYING = re.compile(
    r"^\x01ACTION is (?:playing|editing|watching|listening to) "
    rf"\[https://osu\.(?:{DOMAIN_ESCAPED}|ppy\.sh)/beatmapsets/(?P<sid>\d{{1,10}})#/?(?:osu|taiko|fruits|mania)?/(?P<bid>\d{{1,10}})/? .+\]"
    r"(?: <(?P<mode_vn>Taiko|CatchTheBeat|osu!mania)>)?"
    r"(?P<mods>(?: (?:-|\+|~|\|)\w+(?:~|\|)?)+)?\x01$",
)

SCALED_DURATION = re.compile(r"^(?P<duration>\d{1,6})" r"(?P<scale>s|m|h|d|w)$")

TOURNEY_MATCHNAME = re.compile(
    r"^(?P<name>[a-zA-Z0-9_ ]+): "
    r"\((?P<T1>[a-zA-Z0-9_ ]+)\)"
    r" vs\.? "
    r"\((?P<T2>[a-zA-Z0-9_ ]+)\)$",
    flags=re.IGNORECASE,
)

MAPPOOL_PICK = re.compile(r"^([a-zA-Z]+)([0-9]+)$")

BEST_OF = re.compile(r"^(?:bo)?(\d{1,2})$")
