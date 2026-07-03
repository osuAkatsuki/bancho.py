# bancho.py

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/osuAkatsuki/bancho.py/master.svg)](https://results.pre-commit.ci/latest/github/osuAkatsuki/bancho.py/master)
[![Discord](https://discordapp.com/api/guilds/748687781605408908/widget.png?style=shield)](https://discord.gg/ShEQgUx)

[English](README.md) · 简体中文 · [Italiano](README_IT.md) · [Deutsch](README_DE.md) · [Русский](README_RU.md)

**bancho.py** 是一个 osu! 私服后端，面向各种经验水平、
想要搭建自己的 osu! 私服实例的开发者。

本项目主要由 [Akatsuki](https://akatsuki.gg/) 团队开发，
我们的目标是打造最易维护、最可靠、功能最丰富的 osu! 服务端实现。
它旨在比 Akatsuki.gg 所使用的技术栈更易于部署和修改，
在保留全部核心功能的同时，仍然能够支撑大量玩家同时在线。

如果你有兴趣运行 **bancho.py** 或参与贡献，请前往 **[bancho.py wiki](https://github.com/osuAkatsuki/bancho.py/wiki)**。

## 网页前端

**bancho.py** 是一个后端服务，本身不包含网站。可以搭配以下前端使用：

- **[bancho-web.ts](https://github.com/osuAkatsuki/bancho-web.ts)**（推荐）——
  基于 bancho.py v2 api 构建的现代 React + TypeScript 前端，包含排行榜、
  玩家个人主页、谱面页面、战队、玩家搜索，以及网页注册和登录
  （支持可选的人机验证）。由 bancho.py 团队维护。
- **[guweb](https://github.com/varkaria/guweb)**（备选）——
  由社区长期维护的 python 前端，直接读写 bancho.py 的数据库。

## 许可证

**bancho.py** 基于 [MIT 许可证](https://opensource.org/license/mit/) 发布。详情请参阅 [LICENSE](https://github.com/osuAkatsuki/bancho.py/blob/master/LICENSE) 文件。
