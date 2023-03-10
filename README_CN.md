# bancho.py - 中文文档
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/osuAkatsuki/bancho.py/master.svg)](https://results.pre-commit.ci/latest/github/osuAkatsuki/bancho.py/master)
[![Discord](https://discordapp.com/api/guilds/748687781605408908/widget.png?style=shield)](https://discord.gg/ShEQgUx)

The English version: [[English]](https://github.com/osuAkatsuki/bancho.py/blob/master/README.md)

这是中文翻译哦~由 [hedgehog-qd](https://github.com/hedgehog-qd) 在根据原英语文档部署成功后翻译的。这里
我根据我当时遇到的问题补充了一些提示，如有错误请指正，谢谢！

bancho.py 是一个还在被不断维护的osu!后端项目，不论你的水平如何，都
可以去使用他来开一个自己的osu!私服！

这个项目最初是由 [Akatsuki](https://akatsuki.pw/) 团队开发的,我们的目标是创建一个非常容易
维护并且功能很丰富的osu!私服的服务端！

注意：bancho.py是一个后端！当你跟着下面的步骤部署完成后你可以正常登录
并游玩。这个项目自带api，但是没有前端(就是网页)，前端的话你也可以去看
他们团队开发的前端项目。
api文档(英语)：https://github.com/JKBGL/gulag-api-docs
前端(guweb)：https://github.com/Varkaria/guweb

# 如何在自己的服务器上部署
如果你学习过有关于Linux / 数据库(MySQL) / Python的知识，他们会对你的部署
有很大的帮助！但是这并 不 必须

(有很多没有上面相关知识的朋友也成功的部署了这个项目！)

如果在部署的时候遇到了什么问题，欢迎来我们的Discord群组！(看上面)  :)

这个教程是基于Ubuntu Linux操作系统的，如果你采用了其他操作系统可能会有一点不同~
## 你需要先准备好下面的东西哦~ (译者注)
- 一个服务器*，他可以是你本地的服务器，也可以是一个云服务器
- 一个你自己的域名！注意必须是一级域名！建议在部署前先去开以下的几个子域名(先解析到你的服务器)，后期会方便一些：
 a , b , c , ce , c4 , osu , api , assets

举个例子：如果你购买的域名是 example.com，你就需要去开这些子域名:
a.example.com
b.example.com
c.example.com
等等......

*(注意！如果你在 中国大陆 并且想要和你的朋友一起玩你的私服，译者建议你购买(大陆外的，例如笔者购买的是香港的)云服务器。因为中国大陆的家庭宽带封锁了80和443端口，而且大多数家庭没有公网ipv4，会给后期部署带来麻烦)
*(译者购买的云服务器配置是 2核CPU, 2GB RAM, 30MB带宽，性能足够10人同时在线游玩，仅供配置参考)

## 第一步：下载这个项目到你服务器本地
```sh
# 克隆 bancho.py's
# 注意！你的服务器可能需要先安装git，尤其是全新的服务器
git clone https://github.com/osuAkatsuki/bancho.py

# 进入到 bancho.py 的目录
cd bancho.py
```

## 第二步：安装bancho.py所需的依赖
bancho.py 的代码库有大约15,000行，我们致力于减少我们需要的外部依赖(dependence)

但是你还是需要安装这些哦：(别急！一步步来)
- python (bancho.py就是拿这个写的~)
- mysql (数据库~)
- redis (一种缓存数据库，与mysql不同的是，他把频繁的数据存储到缓存中，读取速度更快)
- nginx (用于反向代理)
- certbot (用于搞SSL证书)
- build-essential ( c/c++ 的 build tools )

当然还有些别的，跟着下面的步骤走就可以全都安装咯~
```sh
# python3.9 现在并不能直接装,
# 这里我们拿deadsnakes来搞
# https://github.com/deadsnakes/python3.9
sudo add-apt-repository -y ppa:deadsnakes

# 安装所有的依赖(dependence)
sudo apt install -y python3.9-dev python3.9-distutils \
                    build-essential \
                    mysql-server redis-server \
                    nginx certbot


# 安装python的包管理器, pip
# pip是用来安装和python有关的包
wget https://bootstrap.pypa.io/get-pip.py
python3.9 get-pip.py && rm get-pip.py

# 更新python3.9和pip到最新
python3.9 -m pip install -U pip setuptools pipenv

# 安装所有bancho.py使用的与python有关的包(外部依赖)
# (如果你想要使用开发环境，那么下面请使用`make install-dev`)
make install
```

## 第三步：给bancho.py开一个数据库！
你需要给bancho.py开一个数据库去存相关的数据：

元数据(metadata) 以及 日志(logs), 例如：用户账户和统计(user accounts
and stats), 譜面(beatmaps and beatmapsets), 聊天(chat channels)等等

```sh
# 开启数据库服务
sudo service mysql start

# 以 root 用户登录mysql（注意如果你已经是root用户的话直接输mysql
# 然后回车就可以啦）

# 现在请小心谨慎，因为你给他的错误命令他会在很短的时间内执行完毕，
# 不给你后悔的机会

sudo mysql
```

现在，我们会：
- 创建一个数据库
- 创建用户
- 给你新建的用户放全部的数据库权限

不要忘记分号(";")哦~
(一会我们会去改bancho.py的配置文件来连接这个数据库)
```sql
# ！你需要改这些东西并且 记 好 他 们 ！:
# - YOUR_DB_NAME       -> 改成你想创建的数据库名字
# - YOUR_DB_USER       -> 改成你想创建的数据库用户名
# - YOUR_DB_PASSWORD   -> 改成你希望的数据库密码

# 给bancho.py创建一个数据库
CREATE DATABASE YOUR_DB_NAME;

# 创建一个操作这个数据库的用户
CREATE USER 'YOUR_DB_USER'@'localhost' IDENTIFIED BY 'YOUR_DB_PASSWORD';

# 给用户放所有的权限让他可以去操作数据库
GRANT ALL PRIVILEGES ON YOUR_DB_NAME.* TO 'YOUR_DB_USER'@'localhost';

# 确保上面的权限变更已经操作好了
FLUSH PRIVILEGES;

# 退出mysql，回到系统命令行
quit
```

## 第四步：把刚刚我们新建的空数据库变成我们想要的样子
我们现在已经建立了一个空的数据库。你可以把数据库理解成一个巨大的表格

bancho.py 有很多 表 (tables) 去存各种东西, 例如, 名为 `users` 以及 `scores`
的表用来存储他们相关的东西（字面意思）

有很多 列 (columns) (竖直的) 存着 `user` or `score`里面不同的数据

这个地方你可以直接把他理解成写着全班同学成绩的成绩表，最上面横行是姓
名，分数，竖着往下看是不同同学的分

有一个基础模板存在 `ext/base.sql`；他可以把我们刚刚新建的数据库搞成我们
想要的样子：
```sh
# 你需要改这些:
# - YOUR_DB_NAME  -> 改成你刚刚创建的数据库名字
# - YOUR_DB_USER  -> 改成你刚刚创建的数据库用户名

# 把bancho.py的数据库框架导入到我们刚刚创建的新数据库

mysql -u YOUR_DB_USER -p YOUR_DB_NAME < migrations/base.sql
```

## 第五步：搞一个SSL证书！ (这样我们就有https啦！)
```sh
# 你需要改这些:
# - YOUR_EMAIL_ADDRESS   -> 改成你的邮箱地址
# - YOUR_DOMAIN          -> 改成你自己的域名

# 下面的指令会给我们搞一个SSL证书
sudo certbot certonly \
    --manual \
    --preferred-challenges=dns \
    --email YOUR_EMAIL_ADDRESS \
    --server https://acme-v02.api.letsencrypt.org/directory \
    --agree-tos \
    -d *.YOUR_DOMAIN
```

## 第六步：配置反向代理 (我们使用Nginx)
bancho.py 需要使用反向代理来使用https，在这里我们使用Nginx这个开源的
web服务器。当然，你也可以尝试一下其他的例如 caddy 以及 h2o.

```sh
# 把nginx配置文件样例复制到 /etc/nginx/sites-available,
# 然后建立符号连接到 /etc/nginx/sites-enabled
sudo cp ext/nginx.conf /etc/nginx/sites-available/bancho.conf
sudo ln -s /etc/nginx/sites-available/bancho.conf /etc/nginx/sites-enabled/bancho.conf

# 现在你可以去编辑配置文件咯
# 你需要更改的地方已经被标识在文件里了
sudo nano /etc/nginx/sites-available/bancho.conf

# 重载配置文件
sudo nginx -s reload
```

## 第七步：配置 bancho.py
你可以在 `.env` 文件里解决所有与bancho.py程序相关的配置
我们提供了一个样例文件 `.env.example`，你可以参考它来设置你自己的
```sh
# 把我们提供的样例文件制造一个副本，直接编辑他就可以了。你所有需要改
# 的地方都在里面有标注/空缺。不用担心，就算你失败了，你也可以再来一次
cp .env.example .env

# 你需要 至少 修改 DB_DSN (*就是数据库连接的URL),
# 如果你想要查看譜面信息，那么请把osu_api_key给填上(在osu官网可以申请)

# 打开配置文件来编辑：
nano .env
```

- *这里设定数据库URL是一个重点！参考下面的来设定！(直接把中文替换即可)
DB_DSN=mysql://数据库用户名:数据库密码@localhost:3306/数据库的名字

## 最后一步啦！运行bancho.py吧！

如果前面的设定都没问题，那么你输入下面的指令就可以运行私服啦！

```sh
# 运行私服啦
make run
```

如果你看到了下面的提示，那么恭喜！你成功了

![tada](https://cdn.discordapp.com/attachments/616400094408736779/993705619498467369/ld-iZXysVXqwhM8.png)

# 文件目录
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
