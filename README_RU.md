# bancho.py

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/osuAkatsuki/bancho.py/master.svg)](https://results.pre-commit.ci/latest/github/osuAkatsuki/bancho.py/master)
[![Discord](https://discordapp.com/api/guilds/748687781605408908/widget.png?style=shield)](https://discord.gg/ShEQgUx)

[English](README.md) · [简体中文](README_CN.md) · [Italiano](README_IT.md) · [Deutsch](README_DE.md) · Русский

**bancho.py** — это бэкенд приватного osu!-сервера для разработчиков любого
уровня опыта, желающих запустить собственный приватный osu!-сервер.

Проект разрабатывается в основном командой [Akatsuki](https://akatsuki.gg/),
и наша цель — создать самую простую в поддержке, надёжную и богатую
возможностями реализацию osu!-сервера. Она задумана более простой в
развёртывании и доработке, чем технологический стек Akatsuki.gg, сохраняя
при этом все ключевые возможности и способность выдерживать большое число
игроков онлайн одновременно.

Если вы хотите запустить **bancho.py** или внести свой вклад, загляните в **[вики bancho.py](https://github.com/osuAkatsuki/bancho.py/wiki)**.

## Веб-фронтенд

**bancho.py** — это только бэкенд, сайт в него не входит. Варианты фронтенда:

- **[bancho-web.ts](https://github.com/osuAkatsuki/bancho-web.ts)** (рекомендуется) —
  современный фронтенд на React + TypeScript, построенный на v2 api bancho.py:
  таблицы лидеров, профили игроков, страницы карт, кланы, поиск игроков, а также
  регистрация и вход через сайт (с опциональной поддержкой капчи).
  Поддерживается командой bancho.py.
- **[guweb](https://github.com/varkaria/guweb)** (альтернатива) — давний фронтенд
  на python, поддерживаемый сообществом; работает напрямую с базой данных bancho.py.

## Лицензия

**bancho.py** распространяется по [лицензии MIT](https://opensource.org/license/mit/). Подробности — в файле [LICENSE](https://github.com/osuAkatsuki/bancho.py/blob/master/LICENSE).
