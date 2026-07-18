from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.constants.clientflags import ClientFlags
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.privileges import Privileges
from app.constants.score_statuses import SubmissionStatus
from app.constants.scoring_metrics import ScoringMetric
from app.objects.beatmap import Beatmap
from app.objects.player import Player
from app.objects.score import Grade
from app.objects.score import Score as DomainScore
from app.repositories.clans import Clan
from app.repositories.clans import ClansRepository
from app.repositories.scores import MapScoreListingRow
from app.repositories.scores import MostPlayedMapRow
from app.repositories.scores import PlayerScoreListingRow
from app.repositories.scores import ReplayHeader
from app.repositories.scores import Score as StoredScore
from app.repositories.scores import ScoresRepository
from app.repositories.stats import StatsRepository
from app.repositories.users import User
from app.repositories.users import UsersRepository
from app.services.performance import PerformanceService
from app.services.performance import ScoreParams
from app.services.visibility import can_view_player


class BeatmapFetcher(Protocol):
    def __call__(self, md5: str, set_id: int = -1) -> Awaitable[Beatmap | None]: ...


class PlayerFetcher(Protocol):
    def __call__(self, player_id: int) -> Awaitable[Player | None]: ...


@dataclass(frozen=True)
class ScoreDomainService:
    """Load and operate on mutable score domain objects.

    ``Score`` itself intentionally contains only submission parsing and pure
    calculations. Database access, entity hydration, performance file access,
    leaderboard placement, submission status, and replay-view persistence are
    coordinated here from explicitly supplied dependencies.
    """

    scores: ScoresRepository
    stats: StatsRepository
    fetch_beatmap: BeatmapFetcher
    fetch_player: PlayerFetcher
    performance: PerformanceService
    beatmaps_path: Path

    async def fetch(self, score_id: int) -> DomainScore | None:
        stored_score = await self.scores.fetch_one(id=score_id)
        if stored_score is None:
            return None

        score = DomainScore()
        score.id = stored_score.id
        score.bmap = await self.fetch_beatmap(stored_score.map_md5)
        score.player = await self.fetch_player(stored_score.userid)
        score.sr = 0.0  # TODO: persist star rating with the score.
        score.pp = stored_score.pp
        score.score = stored_score.score
        score.max_combo = stored_score.max_combo
        score.mods = Mods(stored_score.mods)
        score.acc = stored_score.acc
        score.n300 = stored_score.n300
        score.n100 = stored_score.n100
        score.n50 = stored_score.n50
        score.nmiss = stored_score.nmiss
        score.ngeki = stored_score.ngeki
        score.nkatu = stored_score.nkatu
        score.grade = Grade.from_str(stored_score.grade)
        score.perfect = stored_score.perfect == 1
        score.status = SubmissionStatus(stored_score.status)
        score.passed = score.status != SubmissionStatus.FAILED
        score.mode = GameMode(stored_score.mode)
        score.server_time = stored_score.play_time
        score.time_elapsed = stored_score.time_elapsed
        score.client_flags = ClientFlags(stored_score.client_flags)
        score.client_checksum = stored_score.online_checksum

        if score.bmap is not None:
            score.rank = await self.calculate_placement(score)

        return score

    def calculate_performance(
        self,
        score: DomainScore,
        beatmap_id: int,
    ) -> tuple[float, float]:
        score_args = ScoreParams(
            mode=score.mode.as_vanilla,
            mods=int(score.mods),
            combo=score.max_combo,
            ngeki=score.ngeki,
            n300=score.n300,
            nkatu=score.nkatu,
            n100=score.n100,
            n50=score.n50,
            nmiss=score.nmiss,
        )
        result = self.performance.calculate_performances(
            osu_file_path=str(self.beatmaps_path / f"{beatmap_id}.osu"),
            scores=[score_args],
        )[0]
        return result.performance.pp, result.difficulty.stars

    async def calculate_placement(self, score: DomainScore) -> int:
        assert score.bmap is not None

        if score.mode >= GameMode.RELAX_OSU:
            scoring_metric: ScoringMetric = "pp"
            leaderboard_value = score.pp
        else:
            scoring_metric = "score"
            leaderboard_value = score.score

        return await self.scores.fetch_personal_best_leaderboard_rank(
            map_md5=score.bmap.md5,
            mode=score.mode.value,
            scoring_metric=scoring_metric,
            score=leaderboard_value,
        )

    async def calculate_submission_status(self, score: DomainScore) -> None:
        assert score.player is not None
        assert score.bmap is not None

        previous_scores = await self.scores.fetch_many(
            user_id=score.player.id,
            map_md5=score.bmap.md5,
            mode=score.mode.value,
            status=SubmissionStatus.BEST.value,
            include_hidden_players=True,
        )
        if not previous_scores:
            score.status = SubmissionStatus.BEST
            return

        previous_score = previous_scores[0]
        score.prev_best = await self.fetch(previous_score.id)
        assert score.prev_best is not None

        if score.pp > previous_score.pp:
            score.status = SubmissionStatus.BEST
            score.prev_best.status = SubmissionStatus.SUBMITTED
        else:
            score.status = SubmissionStatus.SUBMITTED

    async def increment_replay_views(self, score: DomainScore) -> None:
        # TODO: move replay views to be per-score rather than per-user.
        assert score.player is not None
        await self.stats.increment_replay_views(
            player_id=score.player.id,
            mode=score.mode.value,
        )


@dataclass(frozen=True)
class PlayerScoreWithBeatmap:
    score: PlayerScoreListingRow
    beatmap: Beatmap | None


@dataclass(frozen=True)
class ScoresListing:
    scores: list[StoredScore]
    total_scores: int


@dataclass(frozen=True)
class ScoreWithContext:
    score: StoredScore
    beatmap: Beatmap
    player: User
    clan: Clan | None


@dataclass(frozen=True)
class ScoresService:
    scores: ScoresRepository
    users: UsersRepository
    clans: ClansRepository
    fetch_beatmap: BeatmapFetcher

    async def fetch_scores(
        self,
        *,
        map_md5: str | None,
        mods: int | None,
        status: int | None,
        mode: int | None,
        user_id: int | None,
        page: int,
        page_size: int,
        viewer: User | None,
    ) -> ScoresListing:
        """Fetch a page of scores. Scores of hidden (restricted or
        unverified) players are excluded unless the viewer is staff;
        players can always see their own scores."""
        viewer_is_staff = (
            viewer is not None and viewer.priv & Privileges.STAFF.value != 0
        )
        scores = await self.scores.fetch_many(
            map_md5=map_md5,
            mods=mods,
            status=status,
            mode=mode,
            user_id=user_id,
            page=page,
            page_size=page_size,
            include_hidden_players=viewer_is_staff,
            always_visible_player_id=viewer.id if viewer is not None else None,
        )
        total_scores = await self.scores.fetch_count(
            map_md5=map_md5,
            mods=mods,
            status=status,
            mode=mode,
            user_id=user_id,
            include_hidden_players=viewer_is_staff,
            always_visible_player_id=viewer.id if viewer is not None else None,
        )

        return ScoresListing(scores=scores, total_scores=total_scores)

    async def fetch_score(self, score_id: int) -> StoredScore | None:
        return await self.scores.fetch_one(id=score_id)

    async def fetch_score_with_context(
        self,
        score_id: int,
        *,
        viewer: User | None,
    ) -> ScoreWithContext | None:
        score = await self.scores.fetch_one(id=score_id)
        if score is None:
            return None

        player = await self.users.fetch_one(id=score.userid)
        if player is None:
            return None

        # scores of hidden (restricted or unverified) players are only
        # visible to staff and to the players themselves
        if not can_view_player(
            viewer=viewer,
            target_id=player.id,
            target_priv=player.priv,
        ):
            return None

        # scores are only displayed while the map version they were set
        # on still exists; a map update invalidates them everywhere else
        # (profile & map leaderboard queries inner join maps), so their
        # permalinks are treated as gone too.
        beatmap = await self.fetch_beatmap(score.map_md5)
        if beatmap is None:
            return None

        clan = None
        if player.clan_id:
            clan = await self.clans.fetch_one(id=player.clan_id)

        return ScoreWithContext(
            score=score,
            beatmap=beatmap,
            player=player,
            clan=clan,
        )

    async def fetch_player_scores(
        self,
        *,
        player_id: int,
        mode: GameMode,
        mods: Mods | None,
        strong_mods_equality: bool,
        scope: str,
        limit: int,
        include_loved: bool,
        include_failed: bool,
    ) -> list[PlayerScoreWithBeatmap]:
        rows: list[PlayerScoreWithBeatmap] = []
        for row in await self.scores.fetch_player_score_listing_rows(
            user_id=player_id,
            mode=int(mode),
            mods=int(mods) if mods is not None else None,
            strong_mods_equality=strong_mods_equality,
            scope=scope,
            limit=limit,
            include_loved=include_loved,
            include_failed=include_failed,
        ):
            beatmap = await self.fetch_beatmap(row.map_md5)
            rows.append(
                PlayerScoreWithBeatmap(
                    score=row,
                    beatmap=beatmap,
                ),
            )

        return rows

    async def fetch_player_most_played(
        self,
        *,
        player_id: int,
        mode: GameMode,
        limit: int,
    ) -> list[MostPlayedMapRow]:
        return await self.scores.fetch_most_played_map_rows(
            user_id=player_id,
            mode=int(mode),
            limit=limit,
        )

    async def fetch_map_scores(
        self,
        *,
        map_md5: str,
        mode: GameMode,
        mods: Mods | None,
        strong_mods_equality: bool,
        scope: str,
        limit: int,
    ) -> list[MapScoreListingRow]:
        return await self.scores.fetch_map_score_listing_rows(
            map_md5=map_md5,
            mode=int(mode),
            mods=int(mods) if mods is not None else None,
            strong_mods_equality=strong_mods_equality,
            scope=scope,
            limit=limit,
        )

    async def fetch_replay_header(self, score_id: int) -> ReplayHeader | None:
        return await self.scores.fetch_replay_header(score_id)
