# bancho.py

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/osuAkatsuki/bancho.py/master.svg)](https://results.pre-commit.ci/latest/github/osuAkatsuki/bancho.py/master)
[![Discord](https://discordapp.com/api/guilds/748687781605408908/widget.png?style=shield)](https://discord.gg/ShEQgUx)

[English](README.md) · [简体中文](README_CN.md) · [Italiano](README_IT.md) · Deutsch · [Русский](README_RU.md) · [Español](README_ES.md)

**bancho.py** ist ein Backend für private osu!-Server, gedacht für Entwickler aller
Erfahrungsstufen, die ihre eigene(n) private(n) osu!-Server-Instanz(en) hosten möchten.

Das Projekt wird hauptsächlich vom [Akatsuki](https://akatsuki.gg/)-Team entwickelt.
Unser Ziel ist es, die am einfachsten zu wartende, zuverlässigste und funktionsreichste
verfügbare osu!-Server-Implementierung zu schaffen. Sie soll einfacher zu deployen und
anzupassen sein als der von Akatsuki.gg verwendete Tech-Stack, dabei alle Kernfunktionen
beibehalten und weiterhin eine große Zahl gleichzeitig verbundener Spieler unterstützen.

Wenn du **bancho.py** betreiben oder dazu beitragen möchtest, schau im **[bancho.py-Wiki](https://github.com/osuAkatsuki/bancho.py/wiki)** vorbei.

## Web-Frontend

**bancho.py** ist ein Backend — eine Website ist nicht enthalten. Passende Frontends:

- **[bancho-web.ts](https://github.com/osuAkatsuki/bancho-web.ts)** (empfohlen) — ein modernes
  React + TypeScript-Frontend auf Basis der v2-api von bancho.py, mit Ranglisten, Spielerprofilen,
  Beatmap-Seiten, Clans, Spielersuche sowie Registrierung und Anmeldung über die Website
  (mit optionaler Captcha-Unterstützung). Gepflegt vom bancho.py-Team.
- **[guweb](https://github.com/varkaria/guweb)** (Alternative) — das langjährige, von der
  Community gepflegte Python-Frontend, das direkt mit der Datenbank von bancho.py kommuniziert.

## Lizenz

**bancho.py** ist unter der [MIT-Lizenz](https://opensource.org/license/mit/) lizenziert. Weitere Informationen findest du in der Datei [LICENSE](https://github.com/osuAkatsuki/bancho.py/blob/master/LICENSE).
