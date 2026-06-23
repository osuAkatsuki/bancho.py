from __future__ import annotations

import hashlib
from datetime import date
from datetime import datetime
from ipaddress import IPv4Address
from types import SimpleNamespace
from types import TracebackType
from typing import TypedDict
from typing import cast

import pytest

from app._typing import UNSET
from app.constants.beatmap_statuses import RankedStatus
from app.constants.clientflags import ClientFlags
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.score_statuses import SubmissionStatus
from app.constants.scoring_metrics import ScoringMetric
from app.objects.player import ClientDetails
from app.objects.player import ModeData
from app.objects.player import OsuStream
from app.objects.player import OsuVersion
from app.objects.score import Grade
from app.objects.score import Score
from app.repositories.achievements import Achievement
from app.repositories.scores import FirstPlaceScore
from app.repositories.scores import ScorePerformanceRow
from app.repositories.user_achievements import UserAchievement
from app.usecases import score_submission


class _FirstPlaceScoreFetch(TypedDict):
    map_md5: str
    mode: int
    scoring_metric: ScoringMetric


class _CreatedScore(TypedDict):
    id: int


class _PreviousBestUpdate(TypedDict):
    map_md5: str
    user_id: int
    mode: int


class _CreatedScoreFields(TypedDict):
    map_md5: str
    score: int
    pp: float
    acc: float
    max_combo: int
    mods: int
    n300: int
    n100: int
    n50: int
    nmiss: int
    ngeki: int
    nkatu: int
    grade: str
    status: int
    mode: int
    play_time: datetime
    time_elapsed: int
    client_flags: int
    user_id: int
    perfect: int
    online_checksum: str


class _ScorePerformanceFetch(TypedDict):
    user_id: int
    mode: int


class _StatsPartialUpdate(TypedDict):
    player_id: int
    mode: int
    updates: dict[str, object]


class _MapPartialUpdate(TypedDict):
    id: int
    updates: dict[str, object]


def _md5(value: str) -> str:
    return hashlib.md5(value.encode()).hexdigest()


def _client_details() -> ClientDetails:
    return ClientDetails(
        osu_version=OsuVersion(
            date=date(2024, 1, 2),
            revision=None,
            stream=OsuStream.STABLE,
        ),
        osu_path_md5="osu-path",
        adapters_md5="adapters",
        uninstall_md5=_md5("unique1"),
        disk_signature_md5=_md5("unique2"),
        adapters=["adapter1", "adapter2"],
        ip=IPv4Address("127.0.0.1"),
    )


def _score() -> Score:
    score = Score()
    score.id = 42
    score.n300 = 83
    score.n100 = 14
    score.n50 = 5
    score.ngeki = 23
    score.nkatu = 6
    score.nmiss = 6
    score.score = 26_810
    score.max_combo = 52
    score.perfect = False
    score.grade = Grade.C
    score.mods = Mods.HIDDEN | Mods.RELAX
    score.passed = True
    score.status = SubmissionStatus.BEST
    score.mode = GameMode.RELAX_OSU
    score.client_time = datetime(2024, 1, 1, 12, 0, 0)
    score.server_time = score.client_time
    score.time_elapsed = 13_358
    score.client_flags = ClientFlags(0)
    score.acc = 81.94
    score.pp = 10.448
    score.rank = 1
    score.prev_best = None
    score.client_checksum = ""
    score.player = SimpleNamespace(id=6, name="test-user", restricted=False)
    score.bmap = SimpleNamespace(
        id=315,
        set_id=141,
        md5="1cf5b2c2edfafd055536d2cefcb89c0e",
        plays=1,
        passes=1,
        last_update="2014-05-18 15:41:48",
        status=RankedStatus.Ranked,
        has_leaderboard=True,
        awards_ranked_pp=True,
        embed="[https://osu.cmyui.xyz/b/315 test map]",
        set=SimpleNamespace(url="https://osu.cmyui.xyz/s/141"),
    )
    return score


def _grade_counts(
    *,
    xh: int = 0,
    x: int = 0,
    sh: int = 0,
    s: int = 0,
    a: int = 0,
) -> dict[Grade, int]:
    return {
        Grade.XH: xh,
        Grade.X: x,
        Grade.SH: sh,
        Grade.S: s,
        Grade.A: a,
    }


def _mode_data(
    *,
    tscore: int = 0,
    rscore: int = 0,
    pp: int = 0,
    acc: float = 0.0,
    plays: int = 0,
    playtime: int = 0,
    max_combo: int = 0,
    total_hits: int = 0,
    rank: int = 0,
    grades: dict[Grade, int] | None = None,
) -> ModeData:
    return ModeData(
        tscore=tscore,
        rscore=rscore,
        pp=pp,
        acc=acc,
        plays=plays,
        playtime=playtime,
        max_combo=max_combo,
        total_hits=total_hits,
        rank=rank,
        grades=grades if grades is not None else _grade_counts(),
    )


def _stats() -> tuple[ModeData, ModeData]:
    previous = ModeData(
        tscore=0,
        rscore=0,
        pp=0,
        acc=0.0,
        plays=0,
        playtime=0,
        max_combo=0,
        total_hits=0,
        rank=0,
        grades={},
    )
    current = ModeData(
        tscore=26_810,
        rscore=26_810,
        pp=11,
        acc=81.94,
        plays=1,
        playtime=13,
        max_combo=52,
        total_hits=102,
        rank=1,
        grades={},
    )
    return previous, current


class _FakeReplayFile:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.read_count = 0

    async def read(self) -> bytes:
        self.read_count += 1
        return self.data


class _FakeReplayPlayer:
    def __init__(self, *, restricted: bool = False, online: bool = True) -> None:
        self.id = 6
        self.name = "test-user"
        self.restricted = restricted
        self.is_online = online
        self.restriction_reasons: list[str] = []
        self.restriction_admins: list[object] = []
        self.logged_out = False

    def __repr__(self) -> str:
        return f"<{self.name} ({self.id})>"

    async def restrict(self, admin: object, reason: str) -> None:
        self.restriction_admins.append(admin)
        self.restriction_reasons.append(reason)

    def logout(self) -> None:
        self.logged_out = True
        self.is_online = False


class _FakeAnnounceChannel:
    def __init__(self) -> None:
        self.messages: list[tuple[str, object, bool]] = []

    def send(self, msg: str, sender: object, to_self: bool = False) -> None:
        self.messages.append((msg, sender, to_self))


class _FakeFirstPlaceScoresRepository:
    def __init__(
        self,
        first_place_score: FirstPlaceScore | None = None,
    ) -> None:
        self.first_place_score = first_place_score
        self.calls: list[_FirstPlaceScoreFetch] = []

    async def fetch_first_place_score(
        self,
        *,
        map_md5: str,
        mode: int,
        scoring_metric: ScoringMetric,
    ) -> FirstPlaceScore | None:
        self.calls.append(
            {
                "map_md5": map_md5,
                "mode": mode,
                "scoring_metric": scoring_metric,
            },
        )
        return self.first_place_score


async def test_save_replay_file_writes_passed_replay(tmp_path) -> None:
    score = _score()
    player = _FakeReplayPlayer()
    score.player = player
    replay_data = b"x" * score_submission.MIN_REPLAY_SIZE
    replay_file = _FakeReplayFile(replay_data)
    missing_replay_logs: list[str] = []

    await score_submission.save_replay_file(
        score,
        replay_file=replay_file,
        replays_path=tmp_path,
        restriction_admin=player,
        log_missing_replay=missing_replay_logs.append,
    )

    assert (tmp_path / "42.osr").read_bytes() == replay_data
    assert replay_file.read_count == 1
    assert missing_replay_logs == []
    assert player.restriction_reasons == []
    assert not player.logged_out


async def test_save_replay_file_does_not_read_failed_score(tmp_path) -> None:
    score = _score()
    player = _FakeReplayPlayer()
    score.player = player
    score.passed = False
    replay_file = _FakeReplayFile(b"")
    missing_replay_logs: list[str] = []

    await score_submission.save_replay_file(
        score,
        replay_file=replay_file,
        replays_path=tmp_path,
        restriction_admin=player,
        log_missing_replay=missing_replay_logs.append,
    )

    assert replay_file.read_count == 0
    assert list(tmp_path.iterdir()) == []
    assert missing_replay_logs == []
    assert player.restriction_reasons == []


async def test_save_replay_file_restricts_unrestricted_player_without_replay(
    tmp_path,
) -> None:
    score = _score()
    player = _FakeReplayPlayer()
    admin = _FakeReplayPlayer()
    score.player = player
    replay_file = _FakeReplayFile(b"x" * (score_submission.MIN_REPLAY_SIZE - 1))
    missing_replay_logs: list[str] = []

    await score_submission.save_replay_file(
        score,
        replay_file=replay_file,
        replays_path=tmp_path,
        restriction_admin=admin,
        log_missing_replay=missing_replay_logs.append,
    )

    assert list(tmp_path.iterdir()) == []
    assert missing_replay_logs == [
        "<test-user (6)> submitted a score without a replay!",
    ]
    assert player.restriction_admins == [admin]
    assert player.restriction_reasons == ["submitted score with no replay"]
    assert player.logged_out


async def test_save_replay_file_does_not_restrict_restricted_player_without_replay(
    tmp_path,
) -> None:
    score = _score()
    player = _FakeReplayPlayer(restricted=True)
    score.player = player
    replay_file = _FakeReplayFile(b"x" * (score_submission.MIN_REPLAY_SIZE - 1))
    missing_replay_logs: list[str] = []

    await score_submission.save_replay_file(
        score,
        replay_file=replay_file,
        replays_path=tmp_path,
        restriction_admin=player,
        log_missing_replay=missing_replay_logs.append,
    )

    assert list(tmp_path.iterdir()) == []
    assert missing_replay_logs == [
        "<test-user (6)> submitted a score without a replay!",
    ]
    assert player.restriction_reasons == []
    assert not player.logged_out


def test_notify_score_submitter_sends_pp_notification() -> None:
    score = _score()
    notifications: list[tuple[object, str]] = []

    performance = score_submission.notify_score_submitter_of_personal_best(
        score,
        send_notification=lambda player, message: notifications.append(
            (player, message),
        ),
    )

    assert performance == "10.45pp"
    assert notifications == [
        (score.player, "You achieved #1! (10.45pp)"),
    ]


def test_notify_score_submitter_uses_score_for_vanilla_loved() -> None:
    score = _score()
    score.bmap.status = RankedStatus.Loved
    score.mode = GameMode.VANILLA_OSU
    score.score = 1_234_567
    notifications: list[tuple[object, str]] = []

    performance = score_submission.notify_score_submitter_of_personal_best(
        score,
        send_notification=lambda player, message: notifications.append(
            (player, message),
        ),
    )

    assert performance == "1,234,567 score"
    assert notifications == [
        (score.player, "You achieved #1! (1,234,567 score)"),
    ]


def test_notify_score_submitter_uses_pp_for_relax_loved() -> None:
    score = _score()
    score.bmap.status = RankedStatus.Loved
    notifications: list[tuple[object, str]] = []

    performance = score_submission.notify_score_submitter_of_personal_best(
        score,
        send_notification=lambda player, message: notifications.append(
            (player, message),
        ),
    )

    assert performance == "10.45pp"
    assert notifications == [
        (score.player, "You achieved #1! (10.45pp)"),
    ]


def test_notify_score_submitter_skips_non_best_score() -> None:
    score = _score()
    score.status = SubmissionStatus.SUBMITTED
    notifications: list[tuple[object, str]] = []

    performance = score_submission.notify_score_submitter_of_personal_best(
        score,
        send_notification=lambda player, message: notifications.append(
            (player, message),
        ),
    )

    assert performance is None
    assert notifications == []


def test_notify_score_submitter_skips_no_leaderboard() -> None:
    score = _score()
    score.bmap.has_leaderboard = False
    notifications: list[tuple[object, str]] = []

    performance = score_submission.notify_score_submitter_of_personal_best(
        score,
        send_notification=lambda player, message: notifications.append(
            (player, message),
        ),
    )

    assert performance is None
    assert notifications == []


async def test_fetch_previous_first_place_score_uses_score_for_vanilla_loved_score() -> (
    None
):
    score = _score()
    score.bmap.status = RankedStatus.Loved
    score.mode = GameMode.VANILLA_OSU
    scores = _FakeFirstPlaceScoresRepository()

    await score_submission.fetch_previous_first_place_score(score, scores=scores)

    assert scores.calls == [
        {
            "map_md5": "1cf5b2c2edfafd055536d2cefcb89c0e",
            "mode": GameMode.VANILLA_OSU.value,
            "scoring_metric": "score",
        },
    ]


def test_announce_first_place_sends_message_with_previous_first_place() -> None:
    score = _score()
    channel = _FakeAnnounceChannel()

    score_submission.announce_first_place(
        score,
        previous_first_place_score={"id": 9, "name": "old-user"},
        announce_channel=channel,
        domain="osu.cmyui.xyz",
    )

    assert channel.messages == [
        (
            "\x01ACTION achieved #1 on [https://osu.cmyui.xyz/b/315 test map] "
            "+HDRX with 81.94% for 10.45pp. "
            "(Previous #1: [https://osu.cmyui.xyz/u/9 old-user])",
            score.player,
            True,
        ),
    ]


def test_announce_first_place_omits_previous_holder_for_same_player() -> None:
    score = _score()
    score.mods = Mods.NOMOD
    channel = _FakeAnnounceChannel()

    score_submission.announce_first_place(
        score,
        previous_first_place_score={"id": 6, "name": "test-user"},
        announce_channel=channel,
        domain="osu.cmyui.xyz",
    )

    assert channel.messages == [
        (
            "\x01ACTION achieved #1 on [https://osu.cmyui.xyz/b/315 test map] "
            "with 81.94% for 10.45pp.",
            score.player,
            True,
        ),
    ]


def test_announce_first_place_uses_score_for_vanilla_loved_score() -> None:
    score = _score()
    score.bmap.status = RankedStatus.Loved
    score.mode = GameMode.VANILLA_OSU
    score.mods = Mods.NOMOD
    score.score = 1_234_567
    channel = _FakeAnnounceChannel()

    score_submission.announce_first_place(
        score,
        previous_first_place_score=None,
        announce_channel=channel,
        domain="osu.cmyui.xyz",
    )

    assert channel.messages == [
        (
            "\x01ACTION achieved #1 on [https://osu.cmyui.xyz/b/315 test map] "
            "with 81.94% for 1,234,567 score.",
            score.player,
            True,
        ),
    ]


@pytest.mark.parametrize(
    "condition",
    [
        "non_best",
        "rank_two",
        "restricted",
        "no_leaderboard",
    ],
)
def test_announce_first_place_skips_ineligible_scores(condition: str) -> None:
    score = _score()
    if condition == "non_best":
        score.status = SubmissionStatus.SUBMITTED
    elif condition == "rank_two":
        score.rank = 2
    elif condition == "restricted":
        score.player.restricted = True
    elif condition == "no_leaderboard":
        score.bmap.has_leaderboard = False

    channel = _FakeAnnounceChannel()

    score_submission.announce_first_place(
        score,
        previous_first_place_score={"id": 9, "name": "old-user"},
        announce_channel=channel,
        domain="osu.cmyui.xyz",
    )

    assert channel.messages == []


def test_announce_first_place_requires_announce_channel() -> None:
    score = _score()

    with pytest.raises(AssertionError):
        score_submission.announce_first_place(
            score,
            previous_first_place_score=None,
            announce_channel=None,
            domain="osu.cmyui.xyz",
        )


class _FailingAchievements:
    async def fetch_many(self) -> list[Achievement]:
        raise AssertionError("achievements should not be fetched")


class _FailingUserAchievements:
    async def fetch_many(
        self,
        *,
        user_id: int,
    ) -> list[UserAchievement]:
        raise AssertionError("user achievements should not be fetched")

    async def create(
        self,
        user_id: int,
        achievement_id: int,
    ) -> UserAchievement:
        raise AssertionError("user achievements should not be created")


class _FakeAchievements:
    async def fetch_many(self) -> list[Achievement]:
        return [
            {
                "id": 1,
                "file": "osu-skill-pass-4",
                "name": "Insanity Approaches",
                "desc": "You're not twitching, you're just ready.",
                "cond": lambda score, mode_vn: True,
            },
            {
                "id": 2,
                "file": "osu-combo-500",
                "name": "500 Combo",
                "desc": "Achieve a 500 combo.",
                "cond": lambda score, mode_vn: False,
            },
            {
                "id": 3,
                "file": "all-intro-hidden",
                "name": "Blindsight",
                "desc": "I can see just perfectly",
                "cond": lambda score, mode_vn: True,
            },
        ]


class _FakeUserAchievements:
    def __init__(self) -> None:
        self.created_achievement_ids: list[int] = []

    async def fetch_many(
        self,
        *,
        user_id: int,
    ) -> list[UserAchievement]:
        assert user_id == 6
        return [{"userid": 6, "achid": 3}]

    async def create(
        self,
        user_id: int,
        achievement_id: int,
    ) -> UserAchievement:
        assert user_id == 6
        self.created_achievement_ids.append(achievement_id)
        return {"userid": user_id, "achid": achievement_id}


class _FakeTransaction:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.exception_type: type[BaseException] | None = None

    async def __aenter__(self) -> None:
        self.calls.append("transaction_enter")

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.exception_type = exc_type
        self.calls.append("transaction_exit")


class _FakeDatabaseTransactions:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.transactions: list[_FakeTransaction] = []

    def transaction(self) -> _FakeTransaction:
        self.calls.append("transaction")
        transaction = _FakeTransaction(self.calls)
        self.transactions.append(transaction)
        return transaction


class _FakeScoresRepository:
    def __init__(
        self,
        best_scores: list[ScorePerformanceRow] | None = None,
        first_place_score: FirstPlaceScore | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.previous_best_updates: list[_PreviousBestUpdate] = []
        self.created_scores: list[_CreatedScoreFields] = []
        self.best_scores = best_scores if best_scores is not None else []
        self.first_place_score = first_place_score
        self.fetches: list[_ScorePerformanceFetch] = []
        self.first_place_score_fetches: list[_FirstPlaceScoreFetch] = []

    async def create(
        self,
        **score_fields: object,
    ) -> _CreatedScore:
        self.calls.append("create")
        self.created_scores.append(cast(_CreatedScoreFields, score_fields))
        return {"id": 123}

    async def mark_previous_best_scores_submitted(
        self,
        *,
        map_md5: str,
        user_id: int,
        mode: int,
    ) -> None:
        self.calls.append("mark_previous_best_scores_submitted")
        self.previous_best_updates.append(
            {
                "map_md5": map_md5,
                "user_id": user_id,
                "mode": mode,
            },
        )

    async def fetch_weighted_best_performances(
        self,
        *,
        user_id: int,
        mode: int,
    ) -> list[ScorePerformanceRow]:
        self.fetches.append({"user_id": user_id, "mode": mode})
        return self.best_scores

    async def fetch_first_place_score(
        self,
        *,
        map_md5: str,
        mode: int,
        scoring_metric: ScoringMetric,
    ) -> FirstPlaceScore | None:
        self.calls.append("fetch_first_place_score")
        self.first_place_score_fetches.append(
            {
                "map_md5": map_md5,
                "mode": mode,
                "scoring_metric": scoring_metric,
            },
        )
        return self.first_place_score


class _FakeScorePerformanceRepository:
    def __init__(
        self,
        best_scores: list[ScorePerformanceRow] | None = None,
    ) -> None:
        self.best_scores = best_scores if best_scores is not None else []
        self.fetches: list[_ScorePerformanceFetch] = []

    async def fetch_weighted_best_performances(
        self,
        *,
        user_id: int,
        mode: int,
    ) -> list[ScorePerformanceRow]:
        self.fetches.append({"user_id": user_id, "mode": mode})
        return self.best_scores


class _FailingScorePerformanceRepository:
    async def fetch_weighted_best_performances(
        self,
        *,
        user_id: int,
        mode: int,
    ) -> list[ScorePerformanceRow]:
        raise AssertionError("weighted best scores should not be fetched")


class _FakeStatsRepository:
    def __init__(self) -> None:
        self.partial_updates: list[_StatsPartialUpdate] = []

    async def partial_update(
        self,
        player_id: int,
        mode: int,
        **updates: object,
    ) -> None:
        self.partial_updates.append(
            {
                "player_id": player_id,
                "mode": mode,
                "updates": {
                    key: value for key, value in updates.items() if value is not UNSET
                },
            },
        )


class _FakeMapsRepository:
    def __init__(self) -> None:
        self.partial_updates: list[_MapPartialUpdate] = []

    async def partial_update(
        self,
        id: int,
        **updates: object,
    ) -> None:
        self.partial_updates.append(
            {
                "id": id,
                "updates": {
                    key: value for key, value in updates.items() if value is not UNSET
                },
            },
        )


class _FailingMapsRepository:
    async def partial_update(
        self,
        id: int,
        **updates: object,
    ) -> None:
        raise RuntimeError("map update failed")


class _FakeUserStatsPublisher:
    def __init__(self) -> None:
        self.published_players: list[object] = []

    def __call__(self, player: object) -> None:
        self.published_players.append(player)


class _FakePlayer:
    def __init__(
        self,
        *,
        stats: ModeData,
        restricted: bool = False,
    ) -> None:
        self.id = 6
        self.name = "test-user"
        self.restricted = restricted
        self.stats = {GameMode.RELAX_OSU: stats}
        self.recent_scores: dict[GameMode, Score] = {}
        self.updated_rank_modes: list[GameMode] = []

    async def update_rank(self, mode: GameMode) -> int:
        self.updated_rank_modes.append(mode)
        return 7


async def test_persist_submitted_score_demotes_previous_best_before_creating_score() -> (
    None
):
    score = _score()
    score.client_checksum = "client-checksum"
    scores = _FakeScoresRepository()

    score_id = await score_submission.persist_submitted_score(score, scores)

    assert score_id == 123
    assert score.id == 123
    assert scores.calls == ["mark_previous_best_scores_submitted", "create"]
    assert scores.previous_best_updates == [
        {
            "map_md5": "1cf5b2c2edfafd055536d2cefcb89c0e",
            "user_id": 6,
            "mode": GameMode.RELAX_OSU.value,
        },
    ]
    assert scores.created_scores == [
        {
            "map_md5": "1cf5b2c2edfafd055536d2cefcb89c0e",
            "score": 26_810,
            "pp": 10.448,
            "acc": 81.94,
            "max_combo": 52,
            "mods": (Mods.HIDDEN | Mods.RELAX).value,
            "n300": 83,
            "n100": 14,
            "n50": 5,
            "nmiss": 6,
            "ngeki": 23,
            "nkatu": 6,
            "grade": "C",
            "status": SubmissionStatus.BEST.value,
            "mode": GameMode.RELAX_OSU.value,
            "play_time": datetime(2024, 1, 1, 12, 0, 0),
            "time_elapsed": 13_358,
            "client_flags": 0,
            "user_id": 6,
            "perfect": 0,
            "online_checksum": "client-checksum",
        },
    ]


async def test_persist_submitted_score_creates_non_best_score_without_demoting() -> (
    None
):
    score = _score()
    score.status = SubmissionStatus.SUBMITTED
    scores = _FakeScoresRepository()

    await score_submission.persist_submitted_score(score, scores)

    assert scores.calls == ["create"]
    assert scores.previous_best_updates == []
    assert scores.created_scores[0]["status"] == SubmissionStatus.SUBMITTED.value


def test_apply_beatmap_play_stats_counts_passed_score() -> None:
    score = _score()
    score.bmap.plays = 1
    score.bmap.passes = 1

    updates = score_submission.apply_beatmap_play_stats(score)

    assert score.bmap.plays == 2
    assert score.bmap.passes == 2
    assert updates == {
        "plays": 2,
        "passes": 2,
    }


def test_apply_beatmap_play_stats_does_not_count_failed_pass() -> None:
    score = _score()
    score.passed = False
    score.bmap.plays = 1
    score.bmap.passes = 1

    updates = score_submission.apply_beatmap_play_stats(score)

    assert score.bmap.plays == 2
    assert score.bmap.passes == 1
    assert updates == {
        "plays": 2,
        "passes": 1,
    }


async def test_persist_score_submission_stats_updates_ranked_best_score_side_effects() -> (
    None
):
    score = _score()
    stats = _mode_data(
        rscore=1_000,
        max_combo=40,
        grades=_grade_counts(),
    )
    player = _FakePlayer(stats=stats)
    score.player = player
    score.bmap.plays = 1
    score.bmap.passes = 1
    stats_repo = _FakeStatsRepository()
    scores_repo = _FakeScorePerformanceRepository(
        best_scores=[
            {"pp": 100.0, "acc": 98.0},
            {"pp": 50.0, "acc": 95.0},
        ],
    )
    maps_repo = _FakeMapsRepository()
    publish_user_stats = _FakeUserStatsPublisher()

    result = await score_submission.persist_score_submission_stats(
        score,
        stats=stats_repo,
        scores=scores_repo,
        maps=maps_repo,
    )

    assert result.previous_stats.plays == 0
    assert result.current_stats.plays == 1
    assert result.current_stats.playtime == 13
    assert result.current_stats.tscore == 26_810
    assert result.current_stats.total_hits == 102
    assert result.current_stats.max_combo == 52
    assert result.current_stats.rscore == 27_810
    assert result.current_stats.acc == pytest.approx(96.5384615385)
    assert result.current_stats.pp == 148
    assert result.current_stats.rank == 0
    assert result.should_update_rank
    assert result.should_publish_user_stats
    assert player.updated_rank_modes == []
    assert scores_repo.fetches == [
        {
            "user_id": 6,
            "mode": GameMode.RELAX_OSU.value,
        },
    ]
    assert stats_repo.partial_updates == [
        {
            "player_id": 6,
            "mode": GameMode.RELAX_OSU.value,
            "updates": {
                "plays": 1,
                "playtime": 13,
                "tscore": 26_810,
                "total_hits": 102,
                "max_combo": 52,
                "rscore": 27_810,
                "acc": pytest.approx(96.5384615385),
                "pp": 148,
            },
        },
    ]
    assert publish_user_stats.published_players == []
    assert score.bmap.plays == 2
    assert score.bmap.passes == 2
    assert maps_repo.partial_updates == [
        {
            "id": 315,
            "updates": {
                "plays": 2,
                "passes": 2,
            },
        },
    ]
    assert player.recent_scores == {}

    persistence_result = score_submission.ScoreSubmissionPersistenceResult(
        score_id=123,
        previous_stats=result.previous_stats,
        current_stats=result.current_stats,
        previous_first_place_score=None,
        unlocked_achievements=[],
        should_update_rank=result.should_update_rank,
        should_publish_user_stats=result.should_publish_user_stats,
    )
    await score_submission.apply_score_submission_side_effects(
        score,
        persistence_result,
        publish_user_stats=publish_user_stats,
    )

    assert result.current_stats.rank == 7
    assert player.updated_rank_modes == [GameMode.RELAX_OSU]
    assert publish_user_stats.published_players == [player]
    assert player.recent_scores[GameMode.RELAX_OSU] is score


async def test_persist_score_submission_stats_updates_failed_score_without_weighted_stats() -> (
    None
):
    score = _score()
    score.passed = False
    score.status = SubmissionStatus.FAILED
    stats = _mode_data(
        plays=2,
        playtime=5,
        tscore=10,
        total_hits=7,
    )
    player = _FakePlayer(stats=stats)
    score.player = player
    score.bmap.plays = 1
    score.bmap.passes = 1
    stats_repo = _FakeStatsRepository()
    maps_repo = _FakeMapsRepository()
    publish_user_stats = _FakeUserStatsPublisher()

    result = await score_submission.persist_score_submission_stats(
        score,
        stats=stats_repo,
        scores=_FailingScorePerformanceRepository(),
        maps=maps_repo,
    )

    assert result.previous_stats.plays == 2
    assert result.current_stats.plays == 3
    assert result.current_stats.playtime == 18
    assert result.current_stats.tscore == 26_820
    assert result.current_stats.total_hits == 109
    assert not result.should_update_rank
    assert result.should_publish_user_stats
    assert player.updated_rank_modes == []
    assert stats_repo.partial_updates == [
        {
            "player_id": 6,
            "mode": GameMode.RELAX_OSU.value,
            "updates": {
                "plays": 3,
                "playtime": 18,
                "tscore": 26_820,
                "total_hits": 109,
            },
        },
    ]
    assert publish_user_stats.published_players == []
    assert player.recent_scores == {}


async def test_persist_score_submission_stats_skips_public_side_effects_for_restricted_player() -> (
    None
):
    score = _score()
    stats = _mode_data(
        rscore=1_000,
        max_combo=40,
        grades=_grade_counts(),
    )
    player = _FakePlayer(stats=stats, restricted=True)
    score.player = player
    score.bmap.awards_ranked_pp = False
    score.bmap.plays = 1
    score.bmap.passes = 1
    stats_repo = _FakeStatsRepository()
    maps_repo = _FakeMapsRepository()
    publish_user_stats = _FakeUserStatsPublisher()

    result = await score_submission.persist_score_submission_stats(
        score,
        stats=stats_repo,
        scores=_FakeScorePerformanceRepository(),
        maps=maps_repo,
    )

    assert stats_repo.partial_updates != []
    assert not result.should_publish_user_stats
    assert publish_user_stats.published_players == []
    assert score.bmap.plays == 1
    assert score.bmap.passes == 1
    assert maps_repo.partial_updates == []
    assert player.recent_scores == {}


async def test_persist_score_submission_wraps_db_writes_in_transaction() -> None:
    score = _score()
    score.client_checksum = "client-checksum"
    stats = _mode_data(
        rscore=1_000,
        max_combo=40,
        grades=_grade_counts(),
    )
    player = _FakePlayer(stats=stats)
    score.player = player
    database = _FakeDatabaseTransactions()
    scores = _FakeScoresRepository(
        best_scores=[
            {"pp": 100.0, "acc": 98.0},
            {"pp": 50.0, "acc": 95.0},
        ],
        first_place_score={"id": 9, "name": "old-user"},
    )
    maps = _FakeMapsRepository()
    user_achievements = _FakeUserAchievements()

    result = await score_submission.persist_score_submission(
        score,
        database=database,
        scores=scores,
        stats=_FakeStatsRepository(),
        maps=maps,
        achievements=_FakeAchievements(),
        user_achievements=user_achievements,
    )

    assert database.calls == ["transaction", "transaction_enter", "transaction_exit"]
    assert database.transactions[0].exception_type is None
    assert scores.calls == [
        "fetch_first_place_score",
        "mark_previous_best_scores_submitted",
        "create",
    ]
    assert scores.first_place_score_fetches == [
        {
            "map_md5": "1cf5b2c2edfafd055536d2cefcb89c0e",
            "mode": GameMode.RELAX_OSU.value,
            "scoring_metric": "pp",
        },
    ]
    assert maps.partial_updates == [
        {
            "id": 315,
            "updates": {
                "plays": 2,
                "passes": 2,
            },
        },
    ]
    assert user_achievements.created_achievement_ids == [1]
    assert result.score_id == 123
    assert result.previous_first_place_score == {"id": 9, "name": "old-user"}
    assert [achievement["id"] for achievement in result.unlocked_achievements] == [1]
    assert result.should_update_rank
    assert result.should_publish_user_stats
    assert player.updated_rank_modes == []
    assert player.recent_scores == {}


async def test_persist_score_submission_restores_memory_state_on_failure() -> None:
    score = _score()
    score.id = None
    score.client_checksum = "client-checksum"
    score.bmap.plays = 10
    score.bmap.passes = 9
    previous_recent_score = _score()
    stats = _mode_data(
        plays=2,
        playtime=5,
        tscore=10,
        total_hits=7,
        rscore=1_000,
        max_combo=40,
        grades=_grade_counts(a=2),
    )
    player = _FakePlayer(stats=stats)
    player.recent_scores[GameMode.RELAX_OSU] = previous_recent_score
    score.player = player
    database = _FakeDatabaseTransactions()

    with pytest.raises(RuntimeError, match="map update failed"):
        await score_submission.persist_score_submission(
            score,
            database=database,
            scores=_FakeScoresRepository(
                best_scores=[
                    {"pp": 100.0, "acc": 98.0},
                    {"pp": 50.0, "acc": 95.0},
                ],
            ),
            stats=_FakeStatsRepository(),
            maps=_FailingMapsRepository(),
            achievements=_FakeAchievements(),
            user_achievements=_FakeUserAchievements(),
        )

    assert database.calls == ["transaction", "transaction_enter", "transaction_exit"]
    assert database.transactions[0].exception_type is RuntimeError
    assert score.id is None
    assert score.bmap.plays == 10
    assert score.bmap.passes == 9
    assert player.stats[GameMode.RELAX_OSU].plays == 2
    assert player.stats[GameMode.RELAX_OSU].playtime == 5
    assert player.stats[GameMode.RELAX_OSU].tscore == 10
    assert player.stats[GameMode.RELAX_OSU].total_hits == 7
    assert player.stats[GameMode.RELAX_OSU].rscore == 1_000
    assert player.stats[GameMode.RELAX_OSU].max_combo == 40
    assert player.stats[GameMode.RELAX_OSU].grades[Grade.A] == 2
    assert player.recent_scores[GameMode.RELAX_OSU] is previous_recent_score


def test_parse_unique_id_hashes_md5s_submission_unique_ids() -> None:
    unique_id_hashes = score_submission.parse_unique_id_hashes("unique1|unique2")

    assert unique_id_hashes == score_submission.UniqueIdHashes(
        unique_id1_md5=_md5("unique1"),
        unique_id2_md5=_md5("unique2"),
    )


def test_chart_entry_formats_optional_before_and_after_values() -> None:
    assert score_submission.chart_entry("rankedScore", None, 123.45) == (
        "rankedScoreBefore:|rankedScoreAfter:123.45"
    )


def test_format_achievement_string_uses_client_delimiters() -> None:
    assert (
        score_submission.format_achievement_string(
            "osu-combo-500",
            "500 Combo",
            "Achieve a 500 combo.",
        )
        == "osu-combo-500+500 Combo+Achieve a 500 combo."
    )


def test_validate_client_details_accepts_matching_login_and_submission_data() -> None:
    client_details = _client_details()

    score_submission.validate_client_details(
        client_details=client_details,
        osu_version="20240102",
        client_hash=client_details.client_hash,
        unique_id_hashes=score_submission.parse_unique_id_hashes("unique1|unique2"),
    )


def test_validate_client_details_rejects_missing_client_details() -> None:
    with pytest.raises(ValueError, match="missing client details"):
        score_submission.validate_client_details(
            client_details=None,
            osu_version="20240102",
            client_hash="client-hash",
            unique_id_hashes=score_submission.parse_unique_id_hashes("unique1|unique2"),
        )


@pytest.mark.parametrize(
    ("osu_version", "client_hash", "unique_ids", "expected_error"),
    [
        ("20240101", None, "unique1|unique2", "osu! version mismatch"),
        ("20240102", "wrong-hash", "unique1|unique2", "client hash mismatch"),
        ("20240102", None, "wrong|unique2", "unique_id1 mismatch"),
        ("20240102", None, "unique1|wrong", "unique_id2 mismatch"),
    ],
)
def test_validate_client_details_rejects_mismatched_submission_data(
    osu_version: str,
    client_hash: str | None,
    unique_ids: str,
    expected_error: str,
) -> None:
    client_details = _client_details()
    if client_hash is None:
        client_hash = client_details.client_hash

    with pytest.raises(ValueError, match=expected_error):
        score_submission.validate_client_details(
            client_details=client_details,
            osu_version=osu_version,
            client_hash=client_hash,
            unique_id_hashes=score_submission.parse_unique_id_hashes(unique_ids),
        )


def test_validate_submission_integrity_accepts_matching_submission_data() -> None:
    client_details = _client_details()
    score = _score()
    score.client_checksum = score.compute_online_checksum(
        osu_version="20240102",
        osu_client_hash=client_details.client_hash,
        storyboard_checksum="storyboard",
    )

    score_submission.validate_submission_integrity(
        client_details=client_details,
        osu_version="20240102",
        client_hash=client_details.client_hash,
        unique_ids="unique1|unique2",
        score=score,
        storyboard_md5="storyboard",
        submission_beatmap_md5="1cf5b2c2edfafd055536d2cefcb89c0e",
        updated_beatmap_hash="1cf5b2c2edfafd055536d2cefcb89c0e",
    )


def test_validate_submission_integrity_rejects_mismatched_score_checksum() -> None:
    client_details = _client_details()
    score = _score()
    score.client_checksum = "wrong-checksum"

    with pytest.raises(ValueError, match="online score checksum mismatch"):
        score_submission.validate_submission_integrity(
            client_details=client_details,
            osu_version="20240102",
            client_hash=client_details.client_hash,
            unique_ids="unique1|unique2",
            score=score,
            storyboard_md5="storyboard",
            submission_beatmap_md5="1cf5b2c2edfafd055536d2cefcb89c0e",
            updated_beatmap_hash="1cf5b2c2edfafd055536d2cefcb89c0e",
        )


def test_validate_submission_integrity_rejects_mismatched_beatmap_hash() -> None:
    client_details = _client_details()
    score = _score()
    score.client_checksum = score.compute_online_checksum(
        osu_version="20240102",
        osu_client_hash=client_details.client_hash,
        storyboard_checksum="storyboard",
    )

    with pytest.raises(ValueError, match="beatmap hash mismatch"):
        score_submission.validate_submission_integrity(
            client_details=client_details,
            osu_version="20240102",
            client_hash=client_details.client_hash,
            unique_ids="unique1|unique2",
            score=score,
            storyboard_md5="storyboard",
            submission_beatmap_md5="1cf5b2c2edfafd055536d2cefcb89c0e",
            updated_beatmap_hash="wrong-md5",
        )


def test_apply_score_stats_updates_base_stats_for_failed_score() -> None:
    score = _score()
    score.passed = False
    score.mode = GameMode.VANILLA_OSU
    score.time_elapsed = 2_500
    score.score = 1_000
    score.n300 = 3
    score.n100 = 2
    score.n50 = 1
    stats = ModeData(
        tscore=10,
        rscore=20,
        pp=30,
        acc=40.0,
        plays=2,
        playtime=5,
        max_combo=100,
        total_hits=7,
        rank=50,
        grades=_grade_counts(),
    )

    updates = score_submission.apply_score_stats(score, stats)

    assert stats.plays == 3
    assert stats.playtime == 7
    assert stats.tscore == 1_010
    assert stats.total_hits == 13
    assert updates == {
        "plays": 3,
        "playtime": 7,
        "tscore": 1_010,
        "total_hits": 13,
    }


@pytest.mark.parametrize("mode", [GameMode.VANILLA_TAIKO, GameMode.VANILLA_MANIA])
def test_apply_score_stats_counts_taiko_and_mania_bonus_hits_by_mode(
    mode: GameMode,
) -> None:
    score = _score()
    score.passed = False
    score.mode = mode
    stats = _mode_data()

    updates = score_submission.apply_score_stats(score, stats)

    assert stats.total_hits == 131
    assert updates["total_hits"] == 131


def test_apply_score_stats_skips_leaderboard_stats_without_leaderboard() -> None:
    score = _score()
    score.bmap.has_leaderboard = False
    score.score = 50_000
    score.max_combo = 300
    score.grade = Grade.S
    stats = ModeData(
        tscore=0,
        rscore=1_000,
        pp=0,
        acc=0.0,
        plays=0,
        playtime=0,
        max_combo=100,
        total_hits=0,
        rank=0,
        grades=_grade_counts(s=1),
    )

    updates = score_submission.apply_score_stats(score, stats)

    assert stats.max_combo == 100
    assert stats.rscore == 1_000
    assert stats.grades[Grade.S] == 1
    assert "max_combo" not in updates
    assert "rscore" not in updates
    assert "s_count" not in updates


def test_apply_score_stats_updates_max_combo_without_ranked_stats_for_submitted_score() -> (
    None
):
    score = _score()
    score.status = SubmissionStatus.SUBMITTED
    score.score = 50_000
    score.max_combo = 300
    score.grade = Grade.S
    stats = _mode_data(
        rscore=1_000,
        max_combo=100,
        grades=_grade_counts(s=1),
    )

    updates = score_submission.apply_score_stats(score, stats)

    assert stats.max_combo == 300
    assert stats.rscore == 1_000
    assert stats.grades[Grade.S] == 1
    assert updates["max_combo"] == 300
    assert "rscore" not in updates
    assert "s_count" not in updates


def test_apply_score_stats_skips_ranked_stats_for_loved_map() -> None:
    score = _score()
    score.bmap.awards_ranked_pp = False
    score.score = 50_000
    score.max_combo = 300
    score.grade = Grade.S
    stats = _mode_data(
        rscore=1_000,
        max_combo=100,
        grades=_grade_counts(s=1),
    )

    updates = score_submission.apply_score_stats(score, stats)

    assert stats.max_combo == 300
    assert stats.rscore == 1_000
    assert stats.grades[Grade.S] == 1
    assert updates["max_combo"] == 300
    assert "rscore" not in updates
    assert "s_count" not in updates


def test_apply_score_stats_updates_first_best_ranked_score() -> None:
    score = _score()
    score.score = 50_000
    score.max_combo = 300
    score.grade = Grade.S
    stats = ModeData(
        tscore=0,
        rscore=1_000,
        pp=0,
        acc=0.0,
        plays=0,
        playtime=0,
        max_combo=100,
        total_hits=0,
        rank=0,
        grades=_grade_counts(s=1),
    )

    updates = score_submission.apply_score_stats(score, stats)

    assert stats.max_combo == 300
    assert stats.rscore == 51_000
    assert stats.grades[Grade.S] == 2
    assert updates["max_combo"] == 300
    assert updates["rscore"] == 51_000
    assert updates["s_count"] == 2


@pytest.mark.parametrize(
    ("grade", "update_column"),
    [
        (Grade.XH, "xh_count"),
        (Grade.X, "x_count"),
        (Grade.SH, "sh_count"),
        (Grade.S, "s_count"),
        (Grade.A, "a_count"),
    ],
)
def test_apply_score_stats_updates_first_best_grade_column(
    grade: Grade,
    update_column: str,
) -> None:
    score = _score()
    score.score = 50_000
    score.max_combo = 50
    score.grade = grade
    stats = _mode_data(
        rscore=1_000,
        max_combo=100,
    )

    updates = score_submission.apply_score_stats(score, stats)

    assert stats.rscore == 51_000
    assert stats.grades[grade] == 1
    assert updates["rscore"] == 51_000
    assert updates[update_column] == 1
    assert "max_combo" not in updates


def test_apply_score_stats_updates_first_best_ranked_score_without_b_grade_count() -> (
    None
):
    score = _score()
    score.score = 50_000
    score.max_combo = 50
    score.grade = Grade.B
    stats = _mode_data(
        rscore=1_000,
        max_combo=100,
    )

    updates = score_submission.apply_score_stats(score, stats)

    assert stats.rscore == 51_000
    assert updates["rscore"] == 51_000
    assert all(f"{grade.name.lower()}_count" not in updates for grade in Grade)
    assert "max_combo" not in updates


def test_apply_score_stats_replaces_previous_best_ranked_score_and_grades() -> None:
    score = _score()
    score.score = 30_000
    score.max_combo = 50
    score.grade = Grade.S
    previous_best = Score()
    previous_best.score = 20_000
    previous_best.grade = Grade.A
    score.prev_best = previous_best
    stats = ModeData(
        tscore=0,
        rscore=50_000,
        pp=0,
        acc=0.0,
        plays=0,
        playtime=0,
        max_combo=100,
        total_hits=0,
        rank=0,
        grades=_grade_counts(s=1, a=2),
    )

    updates = score_submission.apply_score_stats(score, stats)

    assert stats.rscore == 60_000
    assert stats.grades[Grade.S] == 2
    assert stats.grades[Grade.A] == 1
    assert updates["rscore"] == 60_000
    assert updates["s_count"] == 2
    assert updates["a_count"] == 1
    assert "max_combo" not in updates


def test_apply_score_stats_replaces_previous_a_best_with_b_grade() -> None:
    score = _score()
    score.score = 30_000
    score.max_combo = 50
    score.grade = Grade.B
    previous_best = Score()
    previous_best.score = 20_000
    previous_best.grade = Grade.A
    score.prev_best = previous_best
    stats = _mode_data(
        rscore=50_000,
        max_combo=100,
        grades=_grade_counts(a=2),
    )

    updates = score_submission.apply_score_stats(score, stats)

    assert stats.rscore == 60_000
    assert stats.grades[Grade.A] == 1
    assert updates["rscore"] == 60_000
    assert updates["a_count"] == 1
    assert "b_count" not in updates
    assert "max_combo" not in updates


def test_apply_score_stats_replaces_previous_b_best_with_a_grade() -> None:
    score = _score()
    score.score = 30_000
    score.max_combo = 50
    score.grade = Grade.A
    previous_best = Score()
    previous_best.score = 20_000
    previous_best.grade = Grade.B
    score.prev_best = previous_best
    stats = _mode_data(
        rscore=50_000,
        max_combo=100,
        grades=_grade_counts(a=2),
    )

    updates = score_submission.apply_score_stats(score, stats)

    assert stats.rscore == 60_000
    assert stats.grades[Grade.A] == 3
    assert updates["rscore"] == 60_000
    assert updates["a_count"] == 3
    assert "b_count" not in updates
    assert "max_combo" not in updates


def test_apply_score_stats_keeps_grade_counts_when_previous_best_grade_matches() -> (
    None
):
    score = _score()
    score.score = 30_000
    score.grade = Grade.S
    previous_best = Score()
    previous_best.score = 20_000
    previous_best.grade = Grade.S
    score.prev_best = previous_best
    stats = ModeData(
        tscore=0,
        rscore=50_000,
        pp=0,
        acc=0.0,
        plays=0,
        playtime=0,
        max_combo=100,
        total_hits=0,
        rank=0,
        grades=_grade_counts(s=2),
    )

    updates = score_submission.apply_score_stats(score, stats)

    assert stats.rscore == 60_000
    assert stats.grades[Grade.S] == 2
    assert updates["rscore"] == 60_000
    assert "s_count" not in updates


def test_apply_weighted_performance_stats_calculates_accuracy_and_pp() -> None:
    stats = ModeData(
        tscore=0,
        rscore=0,
        pp=0,
        acc=0.0,
        plays=0,
        playtime=0,
        max_combo=0,
        total_hits=0,
        rank=0,
        grades=_grade_counts(),
    )

    updates = score_submission.apply_weighted_performance_stats(
        stats,
        [
            {"pp": 100.0, "acc": 98.0},
            {"pp": 50.0, "acc": 95.0},
        ],
    )

    assert stats.acc == pytest.approx(96.5384615385)
    assert stats.pp == 148
    assert updates["acc"] == pytest.approx(96.5384615385)
    assert updates["pp"] == 148


def test_build_submission_charts_formats_osu_client_response() -> None:
    score = _score()
    previous_stats, current_stats = _stats()
    achievements = [
        {
            "id": 1,
            "file": "osu-skill-pass-4",
            "name": "Insanity Approaches",
            "desc": "You're not twitching, you're just ready.",
            "cond": lambda score, mode_vn: True,
        },
        {
            "id": 2,
            "file": "all-intro-hidden",
            "name": "Blindsight",
            "desc": "I can see just perfectly",
            "cond": lambda score, mode_vn: True,
        },
    ]

    response = score_submission.build_submission_charts(
        score=score,
        previous_stats=previous_stats,
        current_stats=current_stats,
        achievements=achievements,
        domain="cmyui.xyz",
    )

    assert response == (
        b"beatmapId:315|beatmapSetId:141|beatmapPlaycount:1|beatmapPasscount:1|approvedDate:2014-05-18 15:41:48|\n"
        b"|chartId:beatmap|chartUrl:https://osu.cmyui.xyz/s/141|chartName:Beatmap Ranking|rankBefore:|rankAfter:1|rankedScoreBefore:|rankedScoreAfter:26810|totalScoreBefore:|totalScoreAfter:26810|maxComboBefore:|maxComboAfter:52|accuracyBefore:|accuracyAfter:81.94|ppBefore:|ppAfter:10.448|onlineScoreId:42|\n"
        b"|chartId:overall|chartUrl:https://cmyui.xyz/u/6|chartName:Overall Ranking|rankBefore:|rankAfter:1|rankedScoreBefore:|rankedScoreAfter:26810|totalScoreBefore:|totalScoreAfter:26810|maxComboBefore:|maxComboAfter:52|accuracyBefore:|accuracyAfter:81.94|ppBefore:|ppAfter:11|achievements-new:osu-skill-pass-4+Insanity Approaches+You're not twitching, you're just ready./all-intro-hidden+Blindsight+I can see just perfectly"
    )


def test_build_submission_charts_includes_previous_best_values() -> None:
    score = _score()
    previous_best = Score()
    previous_best.rank = 4
    previous_best.score = 20_000
    previous_best.max_combo = 40
    previous_best.acc = 80.123
    previous_best.pp = 9.5
    score.prev_best = previous_best
    previous_stats, current_stats = _stats()

    response = score_submission.build_submission_charts(
        score=score,
        previous_stats=previous_stats,
        current_stats=current_stats,
        achievements=[],
        domain="cmyui.xyz",
    )

    assert (
        b"rankBefore:4|rankAfter:1|rankedScoreBefore:20000|rankedScoreAfter:26810"
        in response
    )
    assert (
        b"accuracyBefore:80.12|accuracyAfter:81.94|ppBefore:9.5|ppAfter:10.448"
        in response
    )


async def test_build_score_submission_response_returns_error_for_failed_score() -> None:
    score = _score()
    score.passed = False
    previous_stats, current_stats = _stats()

    response = await score_submission.build_score_submission_response(
        score=score,
        previous_stats=previous_stats,
        current_stats=current_stats,
        domain="cmyui.xyz",
        achievements=_FailingAchievements(),
        user_achievements=_FailingUserAchievements(),
    )

    assert response == b"error: no"


@pytest.mark.parametrize(
    ("awards_ranked_pp", "restricted"),
    [
        (False, False),
        (True, True),
    ],
)
async def test_build_score_submission_response_skips_achievements_when_score_is_not_eligible(
    awards_ranked_pp: bool,
    restricted: bool,
) -> None:
    score = _score()
    score.bmap.awards_ranked_pp = awards_ranked_pp
    score.player.restricted = restricted
    previous_stats, current_stats = _stats()

    response = await score_submission.build_score_submission_response(
        score=score,
        previous_stats=previous_stats,
        current_stats=current_stats,
        domain="cmyui.xyz",
        achievements=_FailingAchievements(),
        user_achievements=_FailingUserAchievements(),
    )

    assert b"achievements-new:" in response
    assert b"osu-skill-pass-4" not in response


async def test_build_score_submission_response_unlocks_matching_new_achievements() -> (
    None
):
    score = _score()
    previous_stats, current_stats = _stats()
    user_achievements = _FakeUserAchievements()

    response = await score_submission.build_score_submission_response(
        score=score,
        previous_stats=previous_stats,
        current_stats=current_stats,
        domain="cmyui.xyz",
        achievements=_FakeAchievements(),
        user_achievements=user_achievements,
    )

    assert user_achievements.created_achievement_ids == [1]
    assert (
        b"achievements-new:osu-skill-pass-4+Insanity Approaches+You're not twitching, you're just ready."
        in response
    )
    assert b"osu-combo-500" not in response
    assert b"all-intro-hidden" not in response
