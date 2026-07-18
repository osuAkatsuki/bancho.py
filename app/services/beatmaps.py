from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import TypedDict

import httpx
from tenacity import retry
from tenacity.stop import stop_after_attempt

from app.adapters.database import Database
from app.caches import ApplicationCaches
from app.constants.beatmap_statuses import RankedStatus
from app.constants.gamemodes import GameMode
from app.logging import Ansi
from app.logging import log
from app.objects.beatmap import IGNORED_BEATMAP_CHARS
from app.objects.beatmap import Beatmap
from app.objects.beatmap import BeatmapSet
from app.repositories.maps import MapsRepository


class BeatmapApiResponse(TypedDict):
    data: list[dict[str, Any]] | None
    status_code: int


class BeatmapsService:
    """Look up, cache, update, persist, and download osu! beatmaps."""

    def __init__(
        self,
        *,
        maps: MapsRepository,
        database: Database,
        http_client: httpx.AsyncClient,
        caches: ApplicationCaches,
        beatmaps_path: Path,
        osu_api_key: str | None,
        debug: bool,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.maps = maps
        self.database = database
        self.http_client = http_client
        self.caches = caches
        self.beatmaps_path = beatmaps_path
        self.osu_api_key = osu_api_key
        self.debug = debug
        self.now = now

    @retry(reraise=True, stop=stop_after_attempt(3))
    async def fetch_from_osu_api(self, **params: Any) -> BeatmapApiResponse:
        if self.debug:
            log(f"Doing api (getbeatmaps) request {params}", Ansi.LMAGENTA)

        if self.osu_api_key:
            url = "https://old.ppy.sh/api/get_beatmaps"
            params["k"] = self.osu_api_key
        else:
            url = "https://osu.direct/api/get_beatmaps"

        response = await self.http_client.get(url, params=params)
        response_data = response.json()
        if response.status_code == 200 and response_data:
            return {"data": response_data, "status_code": response.status_code}

        return {"data": None, "status_code": response.status_code}

    @retry(reraise=True, stop=stop_after_attempt(3))
    async def fetch_osu_file(self, beatmap_id: int) -> bytes:
        response = await self.http_client.get(
            f"https://old.ppy.sh/osu/{beatmap_id}",
        )
        response.raise_for_status()
        return response.read()

    def has_expected_osu_file(
        self,
        beatmap_id: int,
        expected_md5: str | None = None,
    ) -> bool:
        osu_file_path = self.beatmaps_path / f"{beatmap_id}.osu"
        if not osu_file_path.exists():
            return False

        if expected_md5 is None:
            return True

        osu_file_md5 = hashlib.md5(osu_file_path.read_bytes()).hexdigest()
        return osu_file_md5 == expected_md5

    def write_osu_file(self, beatmap_id: int, data: bytes) -> None:
        (self.beatmaps_path / f"{beatmap_id}.osu").write_bytes(data)

    async def ensure_osu_file_is_available(
        self,
        beatmap_id: int,
        expected_md5: str | None = None,
    ) -> bool:
        if self.has_expected_osu_file(beatmap_id, expected_md5):
            return True

        try:
            latest_osu_file = await self.fetch_osu_file(beatmap_id)
        except httpx.HTTPStatusError:
            return False
        except Exception:
            log(f"Failed to fetch osu file for {beatmap_id}", Ansi.LRED)
            return False

        self.write_osu_file(beatmap_id, latest_osu_file)
        return True

    async def fetch_by_md5(self, md5: str, set_id: int = -1) -> Beatmap | None:
        beatmap = self._fetch_by_md5_from_cache(md5)

        if beatmap is None:
            if set_id <= 0:
                record = await self.maps.fetch_one(md5=md5)
                if record is not None:
                    set_id = record.set_id
                else:
                    api_data = await self.fetch_from_osu_api(h=md5)
                    if api_data["data"] is None:
                        return None
                    set_id = int(api_data["data"][0]["beatmapset_id"])

            beatmap_set = await self.fetch_set(set_id)
            if beatmap_set is not None:
                return self._fetch_by_md5_from_cache(md5)

        if beatmap is not None and beatmap.set.is_cache_expired(self.now()):
            await self._update_if_available(beatmap.set)

        return beatmap

    async def fetch_by_id(self, beatmap_id: int) -> Beatmap | None:
        beatmap = self._fetch_by_id_from_cache(beatmap_id)

        if beatmap is None:
            record = await self.maps.fetch_one(id=beatmap_id)
            if record is not None:
                set_id = record.set_id
            else:
                api_data = await self.fetch_from_osu_api(b=beatmap_id)
                if api_data["data"] is None:
                    return None
                set_id = int(api_data["data"][0]["beatmapset_id"])

            beatmap_set = await self.fetch_set(set_id)
            if beatmap_set is not None:
                return self._fetch_by_id_from_cache(beatmap_id)

        if beatmap is not None and beatmap.set.is_cache_expired(self.now()):
            await self._update_if_available(beatmap.set)

        return beatmap

    async def fetch_set(self, set_id: int) -> BeatmapSet | None:
        beatmap_set = self.caches.beatmapsets.get(set_id)
        did_api_request = False

        if beatmap_set is None:
            beatmap_set = await self._fetch_set_from_database(set_id)

            if beatmap_set is None:
                beatmap_set = await self._fetch_set_from_osu_api(set_id)
                if beatmap_set is None:
                    return None
                did_api_request = True

        if not did_api_request and beatmap_set.is_cache_expired(self.now()):
            await self._update_if_available(beatmap_set)

        self._cache_set(beatmap_set)
        return beatmap_set

    def _fetch_by_md5_from_cache(self, md5: str) -> Beatmap | None:
        return self.caches.beatmaps.get(md5)

    def _fetch_by_id_from_cache(self, beatmap_id: int) -> Beatmap | None:
        return self.caches.beatmaps.get(beatmap_id)

    async def _fetch_set_from_database(self, set_id: int) -> BeatmapSet | None:
        last_osuapi_check = await self.database.fetch_val(
            "SELECT last_osuapi_check FROM mapsets WHERE id = :set_id",
            {"set_id": set_id},
            column=0,
        )
        if last_osuapi_check is None:
            return None

        beatmap_set = BeatmapSet(
            id=set_id,
            last_osuapi_check=last_osuapi_check,
        )

        for row in await self.maps.fetch_many(set_id=set_id):
            beatmap = Beatmap(
                md5=row.md5,
                id=row.id,
                set_id=row.set_id,
                artist=row.artist,
                title=row.title,
                version=row.version,
                creator=row.creator,
                last_update=row.last_update,
                total_length=row.total_length,
                max_combo=row.max_combo,
                status=RankedStatus(row.status),
                frozen=row.frozen,
                plays=row.plays,
                passes=row.passes,
                mode=GameMode(row.mode),
                bpm=row.bpm,
                cs=row.cs,
                od=row.od,
                ar=row.ar,
                hp=row.hp,
                diff=row.diff,
                filename=row.filename,
                map_set=beatmap_set,
            )

            if not beatmap.filename:
                beatmap.filename = (
                    ("{artist} - {title} ({creator}) [{version}].osu")
                    .format(
                        artist=row.artist,
                        title=row.title,
                        creator=row.creator,
                        version=row.version,
                    )
                    .translate(IGNORED_BEATMAP_CHARS)
                )
                await self.maps.partial_update(
                    beatmap.id,
                    filename=beatmap.filename,
                )

            beatmap_set.maps.append(beatmap)

        return beatmap_set

    async def _fetch_set_from_osu_api(self, set_id: int) -> BeatmapSet | None:
        api_data = await self.fetch_from_osu_api(s=set_id)
        if api_data["data"] is None:
            return None

        beatmap_set = BeatmapSet(id=set_id, last_osuapi_check=self.now())
        frozen_maps = await self.database.fetch_all(
            "SELECT id, status FROM maps WHERE set_id = :set_id AND frozen = 1",
            {"set_id": set_id},
        )
        current_maps = {row["id"]: row["status"] for row in frozen_maps}

        for api_beatmap in api_data["data"]:
            beatmap = Beatmap.__new__(Beatmap)
            beatmap.id = int(api_beatmap["beatmap_id"])

            if beatmap.id in current_maps:
                beatmap.status = RankedStatus(current_maps[beatmap.id])
                beatmap.frozen = True
            else:
                beatmap.frozen = False

            beatmap._parse_from_osuapi_resp(api_beatmap)
            beatmap.passes = 0
            beatmap.plays = 0
            beatmap.set = beatmap_set
            beatmap_set.maps.append(beatmap)

        await self._save_set(beatmap_set)
        return beatmap_set

    async def _update_if_available(self, beatmap_set: BeatmapSet) -> None:
        try:
            api_data = await self.fetch_from_osu_api(s=beatmap_set.id)
        except (httpx.TransportError, httpx.DecodingError):
            return

        if api_data["data"] is not None:
            old_maps = {beatmap.id: beatmap for beatmap in beatmap_set.maps}
            new_maps = {
                int(api_map["beatmap_id"]): api_map for api_map in api_data["data"]
            }
            beatmap_set.last_osuapi_check = self.now()

            updated_maps: list[Beatmap] = []
            map_md5s_to_delete: set[str] = set()

            for old_id, old_map in old_maps.items():
                if old_id not in new_maps:
                    map_md5s_to_delete.add(old_map.md5)
                    continue

                new_map = new_maps[old_id]
                new_ranked_status = RankedStatus.from_osuapi(
                    int(new_map["approved"]),
                )
                if (
                    old_map.md5 != new_map["file_md5"]
                    or old_map.status != new_ranked_status
                ):
                    old_map._parse_from_osuapi_resp(new_map)
                updated_maps.append(old_map)

            for new_id, new_map in new_maps.items():
                if new_id in old_maps:
                    continue

                beatmap = Beatmap.__new__(Beatmap)
                beatmap.id = new_id
                beatmap._parse_from_osuapi_resp(new_map)
                beatmap.frozen = False
                beatmap.passes = 0
                beatmap.plays = 0
                beatmap.set = beatmap_set
                updated_maps.append(beatmap)

            beatmap_set.maps = updated_maps

            if map_md5s_to_delete:
                await self._delete_beatmaps(map_md5s_to_delete)

            await self._save_set(beatmap_set)
        elif api_data["status_code"] in (404, 200):
            if beatmap_set.maps:
                await self._delete_beatmaps(
                    {beatmap.md5 for beatmap in beatmap_set.maps},
                )
            await self.database.execute(
                "DELETE FROM mapsets WHERE id = :set_id",
                {"set_id": beatmap_set.id},
            )

    async def _delete_beatmaps(self, map_md5s: set[str]) -> None:
        await self.database.execute(
            "DELETE FROM maps WHERE md5 IN :map_md5s",
            {"map_md5s": map_md5s},
        )
        await self.database.execute(
            "DELETE FROM scores WHERE map_md5 IN :map_md5s",
            {"map_md5s": map_md5s},
        )

    async def _save_set(self, beatmap_set: BeatmapSet) -> None:
        await self.database.execute(
            "REPLACE INTO mapsets "
            "(id, server, last_osuapi_check) "
            "VALUES (:id, :server, :last_osuapi_check)",
            {
                "id": beatmap_set.id,
                "server": "osu!",
                "last_osuapi_check": beatmap_set.last_osuapi_check,
            },
        )
        await self.database.execute_many(
            "REPLACE INTO maps ("
            "md5, id, server, set_id, "
            "artist, title, version, creator, "
            "filename, last_update, total_length, "
            "max_combo, status, frozen, "
            "plays, passes, mode, bpm, "
            "cs, od, ar, hp, diff"
            ") VALUES ("
            ":md5, :id, :server, :set_id, "
            ":artist, :title, :version, :creator, "
            ":filename, :last_update, :total_length, "
            ":max_combo, :status, :frozen, "
            ":plays, :passes, :mode, :bpm, "
            ":cs, :od, :ar, :hp, :diff"
            ")",
            [
                {
                    "md5": beatmap.md5,
                    "id": beatmap.id,
                    "server": "osu!",
                    "set_id": beatmap.set_id,
                    "artist": beatmap.artist,
                    "title": beatmap.title,
                    "version": beatmap.version,
                    "creator": beatmap.creator,
                    "filename": beatmap.filename,
                    "last_update": beatmap.last_update,
                    "total_length": beatmap.total_length,
                    "max_combo": beatmap.max_combo,
                    "status": beatmap.status,
                    "frozen": beatmap.frozen,
                    "plays": beatmap.plays,
                    "passes": beatmap.passes,
                    "mode": beatmap.mode,
                    "bpm": beatmap.bpm,
                    "cs": beatmap.cs,
                    "od": beatmap.od,
                    "ar": beatmap.ar,
                    "hp": beatmap.hp,
                    "diff": beatmap.diff,
                }
                for beatmap in beatmap_set.maps
            ],
        )

    def _cache_set(self, beatmap_set: BeatmapSet) -> None:
        self.caches.beatmapsets[beatmap_set.id] = beatmap_set
        for beatmap in beatmap_set.maps:
            self.caches.beatmaps[beatmap.md5] = beatmap
            self.caches.beatmaps[beatmap.id] = beatmap
