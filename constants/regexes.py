# -*- coding: utf-8 -*-

import re

from objects import glob # this will 100% become a problem

__all__ = ('osu_ver', 'username', 'email', 'now_playing')

DOMAIN_ESCAPED = glob.config.domain.replace('.', r'\.')

osu_ver = re.compile(
    r'^b(?P<ver>\d{8})(?:\.(?P<subver>\d))?'
    r'(?P<stream>beta|cuttingedge|dev|tourney)?$'
)

username = re.compile(r'^[\w \[\]-]{2,15}$')
email = re.compile(r'^[^@\s]{1,200}@[^@\s\.]{1,30}\.[^@\.\s]{2,24}$')

now_playing = re.compile(
    r'^\x01ACTION is (?:playing|editing|watching|listening to) '
    rf'\[https://osu\.(?:{DOMAIN_ESCAPED}|ppy\.sh)/beatmapsets/(?P<sid>\d{{1,10}})#/?(?:osu|taiko|fruits|mania)?/(?P<bid>\d{{1,10}})/? .+\]'
    r'(?: <(?P<mode_vn>Taiko|CatchTheBeat|osu!mania)>)?'
    r'(?P<mods>(?: (?:-|\+|~|\|)\w+(?:~|\|)?)+)?\x01$'
)

scaled_duration = re.compile(
    r'^(?P<duration>\d{1,6})'
    r'(?P<scale>s|m|h|d|w)$'
)

tourney_matchname = re.compile(
    r'^(?P<name>[a-zA-Z0-9_ ]+): '
    r'\((?P<T1>[a-zA-Z0-9_ ]+)\)'
    r' vs\.? '
    r'\((?P<T2>[a-zA-Z0-9_ ]+)\)$',
    flags=re.IGNORECASE
)

mappool_pick = re.compile(r'^([a-zA-Z]+)([0-9]+)$')
