# 项目结构

    .
    ├── app                   # 服务 - 处理逻辑, 类 和 对象
    |   ├── api                 # 处理外部请求的部分
    |   |   ├── domains           # 外部访问可到达的endpoints (终点,指向web服务的api,此处为url,下译为"终点")
    |   |   |   ├── cho.py        # 处理在这个终点的请求: https://c.cmyui.xyz
    |   |   |   ├── map.py        # 处理在这个终点的请求: https://b.cmyui.xyz
    |   |   |   └── osu.py        # 处理在这个终点的请求: https://osu.cmyui.xyz
    |   |   |
    |   |   ├── v1
    |   |   |   └── api.py          # 处理在这个终点的请求: https://api.cmyui.xyz/v1
    |   |   |
    |   |   ├── v2
    |   |   |   ├── clans.py        # 处理在这个终点的请求: https://api.cmyui.xyz/v2/clans
    |   |   |   ├── maps.py         # 处理在这个终点的请求: https://api.cmyui.xyz/v2/maps
    |   |   |   ├── players.py      # 处理在这个终点的请求: https://api.cmyui.xyz/v2/players
    |   |   |   └── scores.py       # 处理在这个终点的请求: https://api.cmyui.xyz/v2/scores
    |   |   |
    |   |   ├── init_api.py       # 初始化api服务
    |   |   └── middlewares.py    # 围绕终点的逻辑部分(中间件)
    |   |
    |   ├── constants           # 服务器端静态类/对象的数据和逻辑实现
    |   |   ├── clientflags.py    # osu!客户端使用的反作弊flags
    |   |   ├── gamemodes.py      # osu!游戏模式, 支持 relax/autopilot
    |   |   ├── mods.py           # osu!游戏mods
    |   |   ├── privileges.py     # 用户特权(玩家,服主,支持者,开发者等等)
    |   |   └── regexes.py        # 整个代码库中的正则表达式
    |   |
    |   ├── objects             # 服务器端动态类/对象的数据和逻辑实现
    |   |   ├── achievement.py    # 有关个人成就achievement
    |   |   ├── beatmap.py        # 有关个人的谱面
    |   |   ├── channel.py        # 有关个人的聊天频道(chat)
    |   |   ├── clan.py           # 有关个人的地区(clans)
    |   |   ├── collection.py     # 动态类的集合 (存储在内存中)
    |   |   ├── match.py          # 多人比赛
    |   |   ├── menu.py           # (-正在制作中-) 聊天频道中的交互菜单
    |   |   ├── models.py         # api请求主体(bodies)的结构
    |   |   ├── player.py         # 关于个人的players
    |   |   └── score.py          # 有关个人的score
    |   |
    |   ├── state               # 和服务器实时状态有关的对象
    |   |   ├── cache.py          # 为最优化而保存的数据
    |   |   ├── services.py       # 外部依赖实例 (e.g. 数据库)
    |   |   └── sessions.py       # 活动的sessions (players, channels, matches, etc.)
    |   |
    |   ├── bg_loops.py           # 服务运时运行的循环
    |   ├── commands.py           # 在osu!的chat里可用的指令
    |   ├── packets.py            # 用于序列化/反序列化的模块
    |   └── settings.py           # 管理用户设置
    |
    ├── ext                   # 运行服务时使用的外部依赖(内容: nginx的配置文件)
    ├── migrations            # 迁移数据库 - updates to schema
    ├── tools                 # 在bancho.py开发过程中曾经制作出来的工具
    └── main.py               # 运行服务的入口
