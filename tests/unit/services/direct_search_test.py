from __future__ import annotations

import app.services.direct_search as direct_search


class _DirectSearchResponse:
    def __init__(
        self,
        *,
        status_code: int,
        payload: list[direct_search.DirectSearchSetPayload],
    ) -> None:
        self.status_code = status_code
        self.payload = payload

    def json(self) -> list[direct_search.DirectSearchSetPayload]:
        return self.payload


class _DirectSearchFetcher:
    def __init__(self, response: _DirectSearchResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, direct_search.DirectSearchParams]] = []

    async def __call__(
        self,
        url: str,
        *,
        params: direct_search.DirectSearchParams,
    ) -> _DirectSearchResponse:
        self.calls.append((url, params))
        return self.response


async def test_direct_search_normalizes_mirror_response() -> None:
    response = _DirectSearchResponse(
        status_code=200,
        payload=[
            {
                "Artist": "A|rtist",
                "Title": "Title",
                "Creator": "Creator",
                "RankedStatus": 1,
                "LastUpdate": "2024-01-01",
                "SetID": 123,
                "HasVideo": True,
                "ChildrenBeatmaps": [
                    {
                        "DifficultyRating": 5.0,
                        "DiffName": "Hard|Pipe",
                        "CS": 4.0,
                        "OD": 8.0,
                        "AR": 9.0,
                        "HP": 6.5,
                        "Mode": 0,
                    },
                    {
                        "DifficultyRating": 2.5,
                        "DiffName": "Normal",
                        "CS": 3.0,
                        "OD": 6.0,
                        "AR": 7.0,
                        "HP": 4.5,
                        "Mode": 0,
                    },
                ],
            },
            {
                "Artist": "Skipped",
                "Title": "No children",
                "Creator": "Creator",
                "RankedStatus": 1,
                "LastUpdate": "2024-01-01",
                "SetID": 124,
                "HasVideo": False,
                "ChildrenBeatmaps": None,
            },
        ],
    )
    fetcher = _DirectSearchFetcher(response)
    service = direct_search.DirectSearchService(
        mirror_search_endpoint="https://mirror.test/search",
        fetch_mirror_search=fetcher,
    )

    result = await service.search(
        ranked_status=0,
        query="camellia",
        mode=0,
        page_num=2,
    )

    assert result.code is direct_search.DirectSearchResultCode.FOUND
    assert result.result_count == 2
    assert fetcher.calls == [
        (
            "https://mirror.test/search",
            {"amount": 100, "offset": 200, "query": "camellia", "mode": 0, "status": 1},
        ),
    ]
    assert result.beatmap_sets is not None
    assert len(result.beatmap_sets) == 1
    beatmap_set = result.beatmap_sets[0]
    assert beatmap_set.artist == "AIrtist"
    assert beatmap_set.has_video == 1
    assert [beatmap.name for beatmap in beatmap_set.beatmaps] == [
        "Normal",
        "HardIPipe",
    ]
