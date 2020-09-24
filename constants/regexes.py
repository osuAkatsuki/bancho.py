# -*- coding: utf-8 -*-

from re import compile as rcomp

__all__ = ('bancho_domain', 'mapfile', 'now_playing')

bancho_domain = rcomp(r'^c(?:e|[4-6])?\.ppy\.sh$')
mapfile = rcomp(r'^(?P<artist>.+) - (?P<title>.+) \((?P<creator>.+)\) \[(?P<version>.+)\]\.osu$')
now_playing = rcomp(
    r'^\x01ACTION is (?:playing|editing|watching|listening to) '
    r'\[https://osu.ppy.sh/b/(?P<bid>\d{1,7}) .+\]'
    r'(?P<mods>(?: (?:-|\+|~|\|)\w+(?:~|\|)?)+)?\x01$'
)
osu_version = rcomp(r'^b(?P<date>\d{8}(?:\.\d+)?)(?:beta|cuttingedge)?$')
