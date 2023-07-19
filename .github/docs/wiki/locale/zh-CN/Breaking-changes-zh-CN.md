# Breaking changes

## 2023-07-19

## 2023-04-09

The `MIRROR_URL` environment variable has been split into `MIRROR_SEARCH_ENDPOINT` and `MIRROR_DOWNLOAD_ENDPOINT`.

```diff
-MIRROR_URL=https://api.chimu.moe/v1

+# Chimu: https://api.chimu.moe/cheesegull/search - https://api.chimu.moe/v1/download
+# Kitsu: https://kitsu.moe/api/search - https://kitsu.moe/d
+MIRROR_SEARCH_ENDPOINT=https://catboy.best/api/search
+MIRROR_DOWNLOAD_ENDPOINT=https://catboy.best/d
```
