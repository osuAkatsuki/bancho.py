# 设置前请阅读

## 前提条件

了解 Linux、Python 和数据库当然会有帮助，但并不是必需条件。

（很多没有编程经验的人也成功安装过这个服务器！）

如果你在流程中的任何地方卡住了，可以加入上方的公共 Discord :)

本指南面向 Ubuntu；其他发行版的安装流程可能会略有不同。

## 依赖项

**bancho.py** 是一个约 20,000 行的代码库，建立在许多优秀项目之上。

我们会尽量减少依赖，但仍然需要以下组件：

- python（编程语言）
- docker（容器运行时）
- docker compose plugin（容器编排）
- mysql（关系型数据库，通过 docker compose 运行）
- redis（内存数据库，通过 docker compose 运行）
- nginx（HTTP(S) 反向代理）
- certbot（SSL 证书工具）
- uv（Python 项目管理器，本地开发时可选）

以及其他一些组件。
