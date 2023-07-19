# Breaking changes

## 2023-07-19

The behaviour of overall pp and accuracy has changed to encapsulate all of a user's scores rather than their top 100, in order to match Bancho's behaviour. This means a recalculation of user's stats is necessary. bancho.py has a recalculation tool which can be found in tools/recalc.py in order to facilitate this.

## 2023-04-09

The `MIRROR_URL` environment variable has been split into `MIRROR_SEARCH_ENDPOINT` and `MIRROR_DOWNLOAD_ENDPOINT`.

```diff
-MIRROR_URL=https://api.chimu.moe/v1

+# Chimu: https://api.chimu.moe/cheesegull/search - https://api.chimu.moe/v1/download
+# Kitsu: https://kitsu.moe/api/search - https://kitsu.moe/d
+MIRROR_SEARCH_ENDPOINT=https://catboy.best/api/search
+MIRROR_DOWNLOAD_ENDPOINT=https://catboy.best/d
```
