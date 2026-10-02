from __future__ import annotations

from sqlalchemy.sql.expression import ClauseElement

from app.adapters.database import DIALECT
from app.repositories.stats import StatsRepository


class _FakeDatabase:
    def __init__(self) -> None:
        self.queries: list[ClauseElement] = []

    async def execute(self, query: ClauseElement) -> int:
        self.queries.append(query)
        return 0


async def test_increment_replay_views_updates_only_requested_player_mode() -> None:
    database = _FakeDatabase()
    repository = StatsRepository(database)  # type: ignore[arg-type]

    await repository.increment_replay_views(player_id=7, mode=4)

    [query] = database.queries
    compiled = query.compile(dialect=DIALECT)
    assert str(compiled) == (
        "UPDATE stats SET replay_views=(stats.replay_views + :replay_views_1) "
        "WHERE stats.id = :id_1 AND stats.mode = :mode_1"
    )
    assert compiled.params == {"replay_views_1": 1, "id_1": 7, "mode_1": 4}
