# Breaking changes

## 2023-07-19

## 2023-04-09

Die Umgebungsvariable `MIRROR_URL` wurde in `MIRROR_SEARCH_ENDPOINT` und `MIRROR_DOWNLOAD_ENDPOINT` aufgeteilt.

```diff
-MIRROR_URL=https://api.chimu.moe/v1

+# Chimu: https://api.chimu.moe/cheesegull/search - https://api.chimu.moe/v1/download
+# Kitsu: https://kitsu.moe/api/search - https://kitsu.moe/d
+MIRROR_SEARCH_ENDPOINT=https://catboy.best/api/search
+MIRROR_DOWNLOAD_ENDPOINT=https://catbot.best/d
```
