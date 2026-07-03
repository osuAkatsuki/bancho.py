# bancho.py

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/osuAkatsuki/bancho.py/master.svg)](https://results.pre-commit.ci/latest/github/osuAkatsuki/bancho.py/master)
[![Discord](https://discordapp.com/api/guilds/748687781605408908/widget.png?style=shield)](https://discord.gg/ShEQgUx)

[English](README.md) · [简体中文](README_CN.md) · Italiano · [Deutsch](README_DE.md) · [Русский](README_RU.md)

**bancho.py** è un backend per server osu! privati, rivolto a sviluppatori di ogni livello
di esperienza interessati a ospitare le proprie istanze di server privati osu!.

Il progetto è sviluppato principalmente dal team di [Akatsuki](https://akatsuki.gg/),
e il nostro obiettivo è creare l'implementazione di server osu! più facile da mantenere,
affidabile e ricca di funzionalità disponibile. Punta a essere più semplice da installare
e modificare rispetto allo stack tecnologico usato da Akatsuki.gg, mantenendo tutte le
funzionalità principali e la capacità di gestire un gran numero di utenti online simultanei.

Se sei interessato a eseguire o contribuire a **bancho.py**, visita la **[wiki di bancho.py](https://github.com/osuAkatsuki/bancho.py/wiki)**.

## Frontend web

**bancho.py** è un backend: non include un sito web. Per abbinarne uno:

- **[bancho-web.ts](https://github.com/osuAkatsuki/bancho-web.ts)** (consigliato) — un
  frontend moderno in React + TypeScript costruito sulla api v2 di bancho.py, con classifiche,
  profili dei giocatori, pagine delle beatmap, clan, ricerca dei giocatori e registrazione e
  accesso dal sito (con supporto captcha opzionale). Mantenuto dal team di bancho.py.
- **[guweb](https://github.com/varkaria/guweb)** (alternativa) — lo storico frontend
  in python mantenuto dalla community, che comunica direttamente con il database di bancho.py.

## Licenza

**bancho.py** è concesso in licenza sotto la [Licenza MIT](https://opensource.org/license/mit/). Consulta il file [LICENSE](https://github.com/osuAkatsuki/bancho.py/blob/master/LICENSE) per ulteriori informazioni.
