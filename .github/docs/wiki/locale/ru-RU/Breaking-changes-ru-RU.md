# Критические изменения

## 2023-09-25

Переменные окружения `SERVER_HOST` и `SERVER_PORT` переименованы в `APP_HOST` и `APP_PORT` соответственно.

## 2023-09-21

Минимальная версия Python повышена до 3.11.

## 2023-07-19

Поведение общего pp и точности изменено: теперь учитываются все результаты игрока, а не только топ-100, чтобы соответствовать поведению Bancho. Это означает, что потребуется пересчёт статистики игроков. Для этого в bancho.py есть инструмент пересчёта — `tools/recalc.py`.

## 2023-04-09

Переменная окружения `MIRROR_URL` разделена на `MIRROR_SEARCH_ENDPOINT` и `MIRROR_DOWNLOAD_ENDPOINT`.

```diff
-MIRROR_URL=https://api.chimu.moe/v1

+# Chimu: https://api.chimu.moe/cheesegull/search - https://api.chimu.moe/v1/download
+# Kitsu: https://kitsu.moe/api/search - https://kitsu.moe/d
+MIRROR_SEARCH_ENDPOINT=https://catboy.best/api/search
+MIRROR_DOWNLOAD_ENDPOINT=https://catboy.best/d
```
