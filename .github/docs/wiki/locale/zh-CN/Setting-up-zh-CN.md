# 设置

## 下载并安装 osu! 服务器代码库

```sh
# 克隆 bancho.py 仓库
git clone https://github.com/osuAkatsuki/bancho.py

# 进入新创建的 bancho.py 目录
cd bancho.py

# 安装 docker，用于构建和运行应用镜像
sudo apt install -y docker.io docker-compose-plugin

# 可选：安装 uv，用于本地 lint、类型检查和单元测试
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 配置 bancho.py

osu! 服务器（bancho.py）本身的配置都可以通过 `.env` 和 `logging.yaml`
完成。项目为这两个文件都提供了示例文件，你可以以它们为基础按需修改。

```sh
# 从提供的示例创建配置文件
cp .env.example .env

# 从提供的示例创建日志配置文件
cp logging.yaml.example logging.yaml

# 按你的需求配置应用
# 这是继续后续步骤前必须完成的操作
nano .env

# 如果需要，也可以进一步配置日志；
# 默认配置对大多数用户来说应该已经够用。
nano logging.yaml
```

## 配置反向代理（这里使用 nginx）

bancho.py 依赖反向代理来支持 TLS（HTTPS），同时也能让配置更简单。本指南使用
开源且高效的 Web 服务器 nginx；你也可以根据需要了解 caddy、h2o 等其他方案。

```sh
# 安装 nginx
sudo apt install nginx

# 使用 .env 中的值安装 nginx 配置
./scripts/install-nginx-config.sh
```

## 恭喜！你已经完成了 osu! 私服的基本设置

如果一切顺利，现在应该可以启动服务器了：

```sh
# 构建应用
make build

# 运行应用
make run
```

此外，还可以使用以下命令进行检查和维护：

```sh
# 在后台运行应用
make run-bg

# 查看所有运行中容器的日志
make logs

# 运行所有自动化测试
make test

# 不使用 docker，仅运行单元测试子集
make utest

# 运行格式化工具和 linter
make lint

# 运行静态类型检查
make type-check

# 删除本地 uv virtualenv
make uninstall
```
