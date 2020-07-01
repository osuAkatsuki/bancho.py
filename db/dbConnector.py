# -*- coding: utf-8 -*-

# old ugly code i'll rewrite soon..
# probably in async for aika, though

from typing import Tuple, Dict, Optional, Union
from mysql.connector.pooling import MySQLConnectionPool
from mysql.connector import errors

class SQLPool:
    def __init__(self, pool_size: int, config) -> None:
        self.pool = MySQLConnectionPool(
            pool_name = 'Aika',
            pool_size = pool_size,
            pool_reset_session = True,
            autocommit = True,
            **config
        )

    def execute(self, query: str, params: Tuple[Union[str, int, float]]=()) -> Optional[int]:
        if not (cnx := self.pool.get_connection()):
            print('MySQL Error: Failed to retrieve a worker!')

        cursor = cnx.cursor()
        cursor.execute(query, params)

        # Discard result.
        cursor.fetchmany()

        res = cursor.lastrowid
        if cursor: cursor.close()
        if cnx: cnx.close()
        return res

    def fetch(self, query: str, params: Tuple[Union[str, int, float]] = (), _all: bool = False) -> Optional[Dict[str, Union[str, int, float]]]:
        if not (cnx := self.pool.get_connection()):
            print('MySQL Error: Failed to retrieve a worker!')
            return

        cursor = cnx.cursor(dictionary=True)
        cursor.execute(query, params)

        res = cursor.fetchall() if _all else cursor.fetchone()
        if cursor: cursor.close()
        if cnx: cnx.close()
        return res

    def fetchall(self, query: str, params: Tuple[Union[str, int, float]] = ()) -> Optional[Dict[str, Union[str, int, float]]]:
        return self.fetch(query, params, True)
