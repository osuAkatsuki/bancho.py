from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import cast

import httpx

from app.adapters.database import Database
from app.caches import ApplicationCaches
from app.constants.beatmap_statuses import RankedStatus
from app.objects.beatmap import Beatmap
from app.objects.beatmap import BeatmapSet
from app.repositories.maps import Map
from app.repositories.maps import MapsRepository
from app.services.beatmaps import BeatmapsService

NOW = datetime(2025, 1, 1, 12)
OLD = datetime(2024, 1, 1)


class _FakeMapsRepository:
    def __init__(self, records: list[Map] | None = None) -> None:
        self.records = records or []
        self.fetch_one_calls: list[dict[str, object]] = []
        self.fetch_many_calls: list[int] = []
        self.partial_update_calls: list[tuple[int, dict[str, object]]] = []

    async def fetch_one(
        self,
        id: int | None = None,
        md5: str | None = None,
        filename: str | None = None,
    ) -> Map | None:
        self.fetch_one_calls.append({"id": id, "md5": md5, "filename": filename})
        for record in self.records:
            if id is not None and record.id == id:
                return record
            if md5 is not None and record.md5 == md5:
                return record
            if filename is not None and record.filename == filename:
                return record
        return None

    async def fetch_many(self, *, set_id: int) -> list[Map]:
        self.fetch_many_calls.append(set_id)
        return [record for record in self.records if record.set_id == set_id]

    async def partial_update(self, id: int, **updates: object) -> Map | None:
        self.partial_update_calls.append((id, updates))
        return next((record for record in self.records if record.id == id), None)


class _FakeDatabase:
    def __init__(
        self,
        *,
        last_osuapi_check: datetime | None = None,
        frozen_maps: list[dict[str, int]] | None = None,
    ) -> None:
        self.last_osuapi_check = last_osuapi_check
        self.frozen_maps = frozen_maps or []
        self.execute_calls: list[tuple[str, dict[str, object]]] = []
        self.execute_many_calls: list[tuple[str, list[dict[str, object]]]] = []

    async def fetch_val(
        self,
        query: str,
        params: dict[str, object],
        *,
        column: int,
    ) -> datetime | None:
        assert "last_osuapi_check" in query
        assert column == 0
        return self.last_osuapi_check

    async def fetch_all(
        self,
        query: str,
        params: dict[str, object],
    ) -> list[dict[str, int]]:
        assert "frozen = 1" in query
        return self.frozen_maps

    async def execute(self, query: str, params: dict[str, object]) -> None:
        self.execute_calls.append((query, params))

    async def execute_many(
        self,
        query: str,
        params: list[dict[str, object]],
    ) -> None:
        self.execute_many_calls.append((query, params))


class _FakeHttpClient:
    def __init__(
        self,
        responses: list[httpx.Response] | None = None,
        responder: Callable[..., httpx.Response] | None = None,
    ) -> None:
        self.responses = responses or []
        self.responder = responder
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def get(self, url: str, **kwargs: object) -> httpx.Response:
        self.calls.append((url, kwargs))
        if self.responder is not None:
            return self.responder(url, **kwargs)
        return self.responses.pop(0)


def _map_record(
    *,
    beatmap_id: int = 11,
    set_id: int = 22,
    md5: str = "a" * 32,
    filename: str = "Artist - Title (Creator) [Hard].osu",
    last_update: datetime = NOW,
) -> Map:
    return Map(
        id=beatmap_id,
        server="osu!",
        set_id=set_id,
        status=int(RankedStatus.Ranked),
        md5=md5,
        artist="Artist",
        title="Title",
        version="Hard",
        creator="Creator",
        filename=filename,
        last_update=last_update,
        total_length=120,
        max_combo=500,
        frozen=False,
        plays=12,
        passes=10,
        mode=0,
        bpm=180.0,
        cs=4.0,
        ar=9.0,
        od=8.0,
        hp=6.0,
        diff=5.2,
    )


def _api_beatmap(
    *,
    beatmap_id: int = 11,
    set_id: int = 22,
    md5: str = "a" * 32,
    approved: int = 1,
) -> dict[str, object]:
    return {
        "beatmap_id": str(beatmap_id),
        "beatmapset_id": str(set_id),
        "file_md5": md5,
        "artist": "Artist",
        "title": "Title",
        "version": "Hard",
        "creator": "Creator",
        "last_update": "2025-01-01 12:00:00",
        "total_length": "120",
        "max_combo": "500",
        "approved": str(approved),
        "mode": "0",
        "bpm": "180",
        "diff_size": "4",
        "diff_overall": "8",
        "diff_approach": "9",
        "diff_drain": "6",
        "difficultyrating": "5.2",
    }


def _response(status_code: int, *, json: object | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://example.test")
    if json is None:
        return httpx.Response(status_code, request=request)
    return httpx.Response(status_code, json=json, request=request)


def _service(
    tmp_path: Path,
    *,
    maps: _FakeMapsRepository | None = None,
    database: _FakeDatabase | None = None,
    http_client: _FakeHttpClient | None = None,
    caches: ApplicationCaches | None = None,
    osu_api_key: str | None = None,
) -> BeatmapsService:
    return BeatmapsService(
        maps=cast(MapsRepository, maps or _FakeMapsRepository()),
        database=cast(Database, database or _FakeDatabase()),
        http_client=cast(httpx.AsyncClient, http_client or _FakeHttpClient()),
        caches=caches or ApplicationCaches(),
        beatmaps_path=tmp_path,
        osu_api_key=osu_api_key,
        debug=False,
        now=lambda: NOW,
    )


def _beatmap(record: Map, beatmap_set: BeatmapSet) -> Beatmap:
    return Beatmap(
        map_set=beatmap_set,
        md5=record.md5,
        id=record.id,
        set_id=record.set_id,
        artist=record.artist,
        title=record.title,
        version=record.version,
        creator=record.creator,
        last_update=record.last_update,
        total_length=record.total_length,
        max_combo=record.max_combo,
        status=RankedStatus(record.status),
    )


async def test_fetch_by_md5_uses_fresh_per_application_cache(tmp_path: Path) -> None:
    caches = ApplicationCaches()
    record = _map_record()
    beatmap_set = BeatmapSet(id=record.set_id, last_osuapi_check=NOW)
    beatmap = _beatmap(record, beatmap_set)
    beatmap_set.maps.append(beatmap)
    caches.beatmaps[record.md5] = beatmap
    maps = _FakeMapsRepository()
    http_client = _FakeHttpClient()
    service = _service(
        tmp_path,
        maps=maps,
        http_client=http_client,
        caches=caches,
    )

    result = await service.fetch_by_md5(record.md5)

    assert result is beatmap
    assert maps.fetch_one_calls == []
    assert http_client.calls == []


async def test_fetch_by_id_loads_and_caches_entire_set_from_database(
    tmp_path: Path,
) -> None:
    record = _map_record(filename="")
    maps = _FakeMapsRepository([record])
    database = _FakeDatabase(last_osuapi_check=NOW)
    caches = ApplicationCaches()
    service = _service(tmp_path, maps=maps, database=database, caches=caches)

    result = await service.fetch_by_id(record.id)

    assert result is not None
    assert result.id == record.id
    assert result.filename == "Artist - Title (Creator) [Hard].osu"
    assert caches.beatmaps[record.id] is result
    assert caches.beatmaps[record.md5] is result
    assert caches.beatmapsets[record.set_id] is result.set
    assert maps.fetch_many_calls == [record.set_id]
    assert maps.partial_update_calls == [
        (record.id, {"filename": "Artist - Title (Creator) [Hard].osu"}),
    ]


async def test_fetch_by_id_falls_back_to_osu_api_and_preserves_frozen_status(
    tmp_path: Path,
) -> None:
    api_beatmap = _api_beatmap(approved=1)
    http_client = _FakeHttpClient(
        [
            _response(200, json=[api_beatmap]),
            _response(200, json=[api_beatmap]),
        ],
    )
    database = _FakeDatabase(
        frozen_maps=[{"id": 11, "status": int(RankedStatus.Loved)}],
    )
    caches = ApplicationCaches()
    service = _service(
        tmp_path,
        database=database,
        http_client=http_client,
        caches=caches,
        osu_api_key="secret",
    )

    result = await service.fetch_by_id(11)

    assert result is not None
    assert result.status is RankedStatus.Loved
    assert result.frozen is True
    assert caches.beatmaps[11] is result
    assert [call[0] for call in http_client.calls] == [
        "https://old.ppy.sh/api/get_beatmaps",
        "https://old.ppy.sh/api/get_beatmaps",
    ]
    assert http_client.calls[0][1]["params"] == {"b": 11, "k": "secret"}
    assert http_client.calls[1][1]["params"] == {"s": 22, "k": "secret"}
    assert len(database.execute_many_calls) == 1


async def test_expired_set_is_updated_and_removed_maps_are_deleted(
    tmp_path: Path,
) -> None:
    old_record = _map_record(md5="a" * 32, last_update=OLD)
    removed_record = _map_record(
        beatmap_id=12,
        md5="b" * 32,
        last_update=OLD,
    )
    beatmap_set = BeatmapSet(id=22, last_osuapi_check=OLD)
    old_beatmap = _beatmap(old_record, beatmap_set)
    removed_beatmap = _beatmap(removed_record, beatmap_set)
    beatmap_set.maps.extend([old_beatmap, removed_beatmap])
    caches = ApplicationCaches(beatmapsets={22: beatmap_set})
    http_client = _FakeHttpClient(
        [
            _response(
                200,
                json=[
                    _api_beatmap(md5="c" * 32),
                    _api_beatmap(beatmap_id=13, md5="d" * 32),
                ],
            ),
        ],
    )
    database = _FakeDatabase()
    service = _service(
        tmp_path,
        database=database,
        http_client=http_client,
        caches=caches,
    )

    result = await service.fetch_set(22)

    assert result is beatmap_set
    assert {beatmap.id for beatmap in result.maps} == {11, 13}
    assert old_beatmap.md5 == "c" * 32
    deletion_params = [
        params
        for query, params in database.execute_calls
        if query.startswith("DELETE FROM maps")
    ]
    assert deletion_params == [{"map_md5s": {"b" * 32}}]
    assert caches.beatmaps[13].md5 == "d" * 32
    assert len(database.execute_many_calls) == 1


async def test_missing_remote_set_deletes_local_maps_and_set(tmp_path: Path) -> None:
    record = _map_record(last_update=OLD)
    beatmap_set = BeatmapSet(id=22, last_osuapi_check=OLD)
    beatmap_set.maps.append(_beatmap(record, beatmap_set))
    database = _FakeDatabase()
    service = _service(
        tmp_path,
        database=database,
        http_client=_FakeHttpClient([_response(404, json=[])]),
        caches=ApplicationCaches(beatmapsets={22: beatmap_set}),
    )

    result = await service.fetch_set(22)

    assert result is beatmap_set
    assert [query for query, _ in database.execute_calls] == [
        "DELETE FROM maps WHERE md5 IN :map_md5s",
        "DELETE FROM scores WHERE map_md5 IN :map_md5s",
        "DELETE FROM mapsets WHERE id = :set_id",
    ]


async def test_missing_remote_empty_set_still_deletes_set_record(
    tmp_path: Path,
) -> None:
    beatmap_set = BeatmapSet(id=22, last_osuapi_check=OLD)
    database = _FakeDatabase()
    service = _service(
        tmp_path,
        database=database,
        http_client=_FakeHttpClient([_response(404, json=[])]),
        caches=ApplicationCaches(beatmapsets={22: beatmap_set}),
    )

    result = await service.fetch_set(22)

    assert result is beatmap_set
    assert database.execute_calls == [
        ("DELETE FROM mapsets WHERE id = :set_id", {"set_id": 22}),
    ]


async def test_ensure_osu_file_uses_matching_disk_file_without_http(
    tmp_path: Path,
) -> None:
    data = b"already downloaded"
    (tmp_path / "11.osu").write_bytes(data)
    http_client = _FakeHttpClient()
    service = _service(tmp_path, http_client=http_client)

    available = await service.ensure_osu_file_is_available(
        11,
        expected_md5=hashlib.md5(data).hexdigest(),
    )

    assert available is True
    assert http_client.calls == []


async def test_ensure_osu_file_replaces_stale_file(tmp_path: Path) -> None:
    (tmp_path / "11.osu").write_bytes(b"stale")
    latest = b"latest"
    http_client = _FakeHttpClient([_response(200, json=None)])
    http_client.responses[0] = httpx.Response(
        200,
        content=latest,
        request=httpx.Request("GET", "https://example.test"),
    )
    service = _service(tmp_path, http_client=http_client)

    available = await service.ensure_osu_file_is_available(
        11,
        expected_md5=hashlib.md5(latest).hexdigest(),
    )

    assert available is True
    assert (tmp_path / "11.osu").read_bytes() == latest
    assert http_client.calls[0][0] == "https://old.ppy.sh/osu/11"


async def test_ensure_osu_file_returns_false_for_http_error(tmp_path: Path) -> None:
    http_client = _FakeHttpClient(
        [_response(404), _response(404), _response(404)],
    )
    service = _service(tmp_path, http_client=http_client)

    available = await service.ensure_osu_file_is_available(11)

    assert available is False
    assert len(http_client.calls) == 3
    assert not (tmp_path / "11.osu").exists()
