# bancho.py

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/osuAkatsuki/bancho.py/master.svg)](https://results.pre-commit.ci/latest/github/osuAkatsuki/bancho.py/master)
[![Discord](https://discordapp.com/api/guilds/748687781605408908/widget.png?style=shield)](https://discord.gg/ShEQgUx)

English · [简体中文](README_CN.md) · [Italiano](README_IT.md) · [Deutsch](README_DE.md) · [Русский](README_RU.md) · [Español](README_ES.md)

**bancho.py** is a private osu! server backend for developers of all levels
of experience interested in hosting their own osu private server instance(s).

the project is developed primarily by the [Akatsuki](https://akatsuki.gg/) team,
and our aim is to create the most easily maintainable, reliable, and feature-rich
osu! server implementation available. It aims to be simpler to deploy and modify
than the tech stack used by Akatsuki.gg, while maintaining all core features, and
still retaining the ability to reach a large number of concurrent online users.

If you are interested in running or contributing to **bancho.py**, you should head over to the **[bancho.py wiki](https://github.com/osuAkatsuki/bancho.py/wiki)**.

## Web frontend

**bancho.py** is a backend server — it does not include a website. To pair it with one:

- **[bancho-web.ts](https://github.com/osuAkatsuki/bancho-web.ts)** (recommended) — a modern
  React + TypeScript frontend built on bancho.py's v2 api, with leaderboards, player profiles,
  beatmap pages, clans, player search, and website registration & login (with optional captcha
  support). Maintained by the bancho.py team.
- **[guweb](https://github.com/varkaria/guweb)** (alternative) — the long-standing
  community-maintained python frontend, which talks directly to bancho.py's database.

## License

**bancho.py** is licensed under the [MIT License](https://opensource.org/license/mit/). Please see the [LICENSE](https://github.com/osuAkatsuki/bancho.py/blob/master/LICENSE) file for more information.
