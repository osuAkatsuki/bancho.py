# bancho.py

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/osuAkatsuki/bancho.py/master.svg)](https://results.pre-commit.ci/latest/github/osuAkatsuki/bancho.py/master)
[![Discord](https://discordapp.com/api/guilds/748687781605408908/widget.png?style=shield)](https://discord.gg/ShEQgUx)

[English](README.md) · [简体中文](README_CN.md) · [Italiano](README_IT.md) · [Deutsch](README_DE.md) · [Русский](README_RU.md) · Español

**bancho.py** es un backend de servidor privado de osu! para desarrolladores con
diversos niveles de experiencia interesados en alojar sus propias
instancias de un servidor privado de osu!

El proyecto es desarrollado principalmente por el equipo de [Akatsuki](https://akatsuki.gg/),
y nuestro objetivo es crear la implementación de servidor de osu! más fácil de
mantener, más fiable y más completa disponible. Busca ser más sencillo de
desplegar y modificar que el stack tecnológico usado por Akatsuki.gg,
manteniendo todas las funcionalidades principales y conservando la capacidad
de soportar un gran número de usuarios conectados simultáneamente.

Si te interesa ejecutar o contribuir a **bancho.py**, deberías visitar la **[wiki de bancho.py](https://github.com/osuAkatsuki/bancho.py/wiki)**.

## Frontend web

**bancho.py** es un servidor backend — no incluye un sitio web. Para acompañarlo con uno:

- **[bancho-web.ts](https://github.com/osuAkatsuki/bancho-web.ts)** (recomendado) — un
  frontend moderno en React + TypeScript construido sobre la API v2 de bancho.py, con
  tablas de clasificación, perfiles de jugadores, páginas de beatmaps, clanes, búsqueda
  de jugadores, y registro e inicio de sesión desde el sitio web (con soporte opcional
  de captcha). Mantenido por el equipo de bancho.py.
- **[guweb](https://github.com/varkaria/guweb)** (alternativa) — el frontend en Python
  mantenido por la comunidad desde hace tiempo, que accede directamente a la base de
  datos de bancho.py.

## Licencia

**bancho.py** está licenciado bajo la [licencia MIT](https://opensource.org/license/mit/). Consulta el archivo [LICENSE](https://github.com/osuAkatsuki/bancho.py/blob/master/LICENSE) para más información.
