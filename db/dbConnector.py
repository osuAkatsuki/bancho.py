# -*- coding: utf-8 -*-

# old ugly code i'll rewrite soon..
# probably in async for aika, though

from typing import Tuple, Dict, Optional, Union
from mysql.connector.pooling import MySQLConnectionPool
from mysql.connector import errors

SQLParam = Union[str, int, float]
SQLResult = Dict[str, Union[str, int, float]]

class SQLPool:
    def __init__(self, pool_size: int, config) -> None:
        self.pool = MySQLConnectionPool(
            pool_name = 'gulag',
            pool_size = pool_size,
            pool_reset_session = True,
            autocommit = True,
            **config
        )

    def execute(self, query: str, params: Tuple[SQLParam] = ()) -> Optional[int]:
        if not (cnx := self.pool.get_connection()):
            print('MySQL Error: Failed to retrieve a worker!')
            return

        cursor = cnx.cursor()
        cursor.execute(query, params)

        # Discard result.
        cursor.fetchmany()

        res = cursor.lastrowid
        [x.close() for x in (cursor, cnx)]
        return res

    def fetch(self, query: str, params: Tuple[SQLParam] = (),
              _all: bool = False) -> Optional[SQLResult]:
        if not (cnx := self.pool.get_connection()):
            print('MySQL Error: Failed to retrieve a worker!')
            return

        cursor = cnx.cursor(dictionary=True)
        cursor.execute(query, params)

        res = cursor.fetchall() if _all else cursor.fetchone()
        [x.close() for x in (cursor, cnx)]
        return res

    def fetchall(self, query: str, params: Tuple[SQLParam] = ()) -> Optional[SQLResult]:
        return self.fetch(query, params, True)
