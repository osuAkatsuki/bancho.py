from __future__ import annotations

from sqlalchemy.sql.expression import ClauseElement

from app.adapters.database import DIALECT
from app.repositories.relationships import RelationshipsRepository
from app.repositories.relationships import RelationshipType


class _FakeDatabase:
    def __init__(self) -> None:
        self.queries: list[ClauseElement] = []

    async def execute(self, query: ClauseElement) -> int:
        self.queries.append(query)
        return 0


async def test_upsert_atomically_replaces_the_relationship_type() -> None:
    database = _FakeDatabase()
    repository = RelationshipsRepository(database)  # type: ignore[arg-type]

    await repository.upsert(3, 4, RelationshipType.FRIEND)

    [query] = database.queries
    compiled = query.compile(dialect=DIALECT)
    assert str(compiled) == (
        "INSERT INTO relationships (user1, user2, type) "
        "VALUES (:user1, :user2, :type) "
        "ON DUPLICATE KEY UPDATE type = :param_1"
    )
    assert compiled.params == {
        "user1": 3,
        "user2": 4,
        "type": RelationshipType.FRIEND,
        "param_1": RelationshipType.FRIEND,
    }
