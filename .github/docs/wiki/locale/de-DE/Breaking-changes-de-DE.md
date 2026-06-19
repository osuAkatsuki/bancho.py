# Wichtige Änderungen

## 2023-09-25

Die Umgebungsvariablen `SERVER_HOST` und `SERVER_PORT` wurden in `APP_HOST` und `APP_PORT` umbenannt.

## 2023-09-21

Die minimale Python-Version wurde auf 3.11 geändert.

## 2023-07-19

Die Berechnung von Gesamt-PP und Genauigkeit umfasst nun alle Scores eines Benutzers statt nur der Top 100, um dem Verhalten von Bancho zu entsprechen. Dadurch ist eine Neuberechnung der Benutzerstatistiken erforderlich. bancho.py enthält dafür ein Neuberechnungstool unter `tools/recalc.py`.

## 2023-04-09

Die Umgebungsvariable `MIRROR_URL` wurde in `MIRROR_SEARCH_ENDPOINT` und `MIRROR_DOWNLOAD_ENDPOINT` aufgeteilt.

```diff
-MIRROR_URL=https://api.chimu.moe/v1

+# Chimu: https://api.chimu.moe/cheesegull/search - https://api.chimu.moe/v1/download
+# Kitsu: https://kitsu.moe/api/search - https://kitsu.moe/d
+MIRROR_SEARCH_ENDPOINT=https://catboy.best/api/search
+MIRROR_DOWNLOAD_ENDPOINT=https://catbot.best/d
```
