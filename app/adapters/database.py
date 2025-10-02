from __future__ import annotations

from typing import Any
from typing import cast

from databases import Database as _Database
from databases.core import Transaction
from sqlalchemy.dialects.mysql.mysqldb import MySQLDialect_mysqldb
from sqlalchemy.sql.compiler import Compiled
from sqlalchemy.sql.expression import ClauseElement

from app import settings
from app.logging import log
from app.timer import Timer


class MySQLDialect(MySQLDialect_mysqldb):
    default_paramstyle = "named"


DIALECT = MySQLDialect()

MySQLRow = dict[str, Any]
MySQLParams = dict[str, Any] | None
MySQLQuery = ClauseElement | str


def make_dsn(
    dialect: str,
    user: str,
    host: str,
    port: int,
    database: str,
    driver: str | None = None,
    password: str | None = None,
) -> str:
    scheme = dialect
    if driver:
        scheme += f"+{driver}"
    if password:
        password = f":{password}"
    else:
        password = ""

    return f"{scheme}://{user}{password}@{host}:{port}/{database}"


class Database:
    def __init__(self, url: str) -> None:
        self._database = _Database(url)

    async def connect(self) -> None:
        await self._database.connect()

    async def disconnect(self) -> None:
        await self._database.disconnect()

    def _compile(self, clause_element: ClauseElement) -> tuple[str, MySQLParams]:
        compiled: Compiled = clause_element.compile(
            dialect=DIALECT,
            compile_kwargs={"render_postcompile": True},
        )
        return str(compiled), compiled.params

    async def fetch_one(
        self,
        query: MySQLQuery,
        params: MySQLParams = None,
    ) -> MySQLRow | None:
        if isinstance(query, ClauseElement):
            query, params = self._compile(query)

        with Timer() as timer:
            row = await self._database.fetch_one(query, params)

        if settings.DEBUG:
            time_elapsed = timer.elapsed()
            log(
                f"Executed SQL query: {query} {params} in {time_elapsed * 1000:.2f} msec.",
                extra={
                    "query": query,
                    "params": params,
                    "time_elapsed": time_elapsed,
                },
            )

        return dict(row._mapping) if row is not None else None

    async def fetch_all(
        self,
        query: MySQLQuery,
        params: MySQLParams = None,
    ) -> list[MySQLRow]:
        if isinstance(query, ClauseElement):
            query, params = self._compile(query)

        with Timer() as timer:
            rows = await self._database.fetch_all(query, params)

        if settings.DEBUG:
            time_elapsed = timer.elapsed()
            log(
                f"Executed SQL query: {query} {params} in {time_elapsed * 1000:.2f} msec.",
                extra={
                    "query": query,
                    "params": params,
                    "time_elapsed": time_elapsed,
                },
            )

        return [dict(row._mapping) for row in rows]

    async def fetch_val(
        self,
        query: MySQLQuery,
        params: MySQLParams = None,
        column: Any = 0,
    ) -> Any:
        if isinstance(query, ClauseElement):
            query, params = self._compile(query)

        with Timer() as timer:
            val = await self._database.fetch_val(query, params, column)

        if settings.DEBUG:
            time_elapsed = timer.elapsed()
            log(
                f"Executed SQL query: {query} {params} in {time_elapsed * 1000:.2f} msec.",
                extra={
                    "query": query,
                    "params": params,
                    "time_elapsed": time_elapsed,
                },
            )

        return val

    async def execute(self, query: MySQLQuery, params: MySQLParams = None) -> int:
        if isinstance(query, ClauseElement):
            query, params = self._compile(query)

        with Timer() as timer:
            rec_id = await self._database.execute(query, params)

        if settings.DEBUG:
            time_elapsed = timer.elapsed()
            log(
                f"Executed SQL query: {query} {params} in {time_elapsed * 1000:.2f} msec.",
                extra={
                    "query": query,
                    "params": params,
                    "time_elapsed": time_elapsed,
                },
            )

        return cast(int, rec_id)

    # NOTE: this accepts str since current execute_many uses are not using alchemy.
    #       alchemy does execute_many in a single query so this method will be unneeded once raw SQL is not in use.
    async def execute_many(self, query: str, params: list[MySQLParams]) -> None:
        if isinstance(query, ClauseElement):
            query, _ = self._compile(query)

        with Timer() as timer:
            await self._database.execute_many(query, params)

        if settings.DEBUG:
            time_elapsed = timer.elapsed()
            log(
                f"Executed SQL query: {query} {params} in {time_elapsed * 1000:.2f} msec.",
                extra={
                    "query": query,
                    "params": params,
                    "time_elapsed": time_elapsed,
                },
            )

    def transaction(
        self,
        *,
        force_rollback: bool = False,
        **kwargs: Any,
    ) -> Transaction:
        return self._database.transaction(force_rollback=force_rollback, **kwargs)
