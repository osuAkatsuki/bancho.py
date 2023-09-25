# Breaking changes

## 2023-09-25

Die Umgebungsvariable `SERVER_HOST` und `SERVER_PORT` wurden in `APP_HOST` und `APP_PORT` aufgeteilt.

## 2023-09-21

Die minimale Python-Version wurde auf 3.11 geändert.

## 2023-07-19

Die Funktionsweise von Gesamt-PP und Genauigkeit hat sich geändert, um alle Scores eines Benutzers zu umfassen, anstatt die Top 100, um das Verhalten von Bancho zu entsprechen. Dies bedeutet, dass eine Neuberechnung der Statistiken eines Benutzers erforderlich ist. Bancho.py verfügt über ein Neuberechnungstool, das in `tools/utils/recalc.py` zu finden ist, um dies zu erleichtern.

## 2023-04-09

Die Umgebungsvariable `MIRROR_URL` wurde in `MIRROR_SEARCH_ENDPOINT` und `MIRROR_DOWNLOAD_ENDPOINT` aufgeteilt.

```diff
-MIRROR_URL=https://api.chimu.moe/v1

+# Chimu: https://api.chimu.moe/cheesegull/search - https://api.chimu.moe/v1/download
+# Kitsu: https://kitsu.moe/api/search - https://kitsu.moe/d
+MIRROR_SEARCH_ENDPOINT=https://catboy.best/api/search
+MIRROR_DOWNLOAD_ENDPOINT=https://catbot.best/d
```
