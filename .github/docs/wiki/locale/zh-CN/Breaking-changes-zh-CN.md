# 重大变更

## 2023-09-25

`SERVER_HOST` 和 `SERVER_PORT` 环境变量已分别重命名为 `APP_HOST` 和 `APP_PORT`。

## 2023-09-21

最低 Python 版本已改为 3.11。

## 2023-07-19

总 pp 和准确率的计算行为已改为包含用户的所有成绩，而不只是前 100 个成绩，以匹配 Bancho 的行为。因此需要重新计算用户统计数据。bancho.py 提供了一个重新计算工具，可在 `tools/recalc.py` 中找到。

## 2023-04-09

`MIRROR_URL` 环境变量已拆分为 `MIRROR_SEARCH_ENDPOINT` 和 `MIRROR_DOWNLOAD_ENDPOINT`。

```diff
-MIRROR_URL=https://api.chimu.moe/v1

+# Chimu: https://api.chimu.moe/cheesegull/search - https://api.chimu.moe/v1/download
+# Kitsu: https://kitsu.moe/api/search - https://kitsu.moe/d
+MIRROR_SEARCH_ENDPOINT=https://catboy.best/api/search
+MIRROR_DOWNLOAD_ENDPOINT=https://catboy.best/d
```
