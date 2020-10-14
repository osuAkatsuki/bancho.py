# -*- coding: utf-8 -*-

from re import compile as rcomp

__all__ = ('mapfile', 'osu_ver', 'username', 'email', 'now_playing')

mapfile = rcomp(r'^(?P<artist>.+) - (?P<title>.+) \((?P<creator>.+)\) \[(?P<version>.+)\]\.osu$')
osu_ver = rcomp(r'^b(?P<date>\d{8}(?:\.\d+)?)(?:beta|cuttingedge)?$')
username = rcomp(r'^[\w \[\]-]{2,15}$')
email = rcomp(r'^[^@\s]{1,200}@[^@\s\.]{1,30}\.[^@\.\s]{2,24}$')
now_playing = rcomp(
    r'^\x01ACTION is (?:playing|editing|watching|listening to) '
    r'\[https://osu.ppy.sh/b/(?P<bid>\d{1,7}) .+\]'
    r'(?P<mods>(?: (?:-|\+|~|\|)\w+(?:~|\|)?)+)?\x01$'
)
