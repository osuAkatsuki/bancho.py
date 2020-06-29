# -*- coding: utf-8 -*-

from typing import Tuple, Dict, Optional, Union
from mysql.connector import errors
from mysql.connector import pooling

class SQLPool:
    def __init__(self, pool_size: int, config: Dict[str, str]) -> None:
        self.pool = pooling.MySQLConnectionPool(
            pool_name = 'Aika',
            pool_size = pool_size,
            pool_reset_session = True,
            autocommit = True,
            **config
        )

    def execute(self, query: str, params: Tuple[Union[str, int, float]]=()) -> Optional[int]:
        cnx = self.pool.get_connection()
        if not cnx:
            print('MySQL Error: Failed to retrieve a worker!')
            return None

        cursor = cnx.cursor()
        cursor.execute(query, params)

        # Discard result.
        cursor.fetchmany()

        res = cursor.lastrowid
        if cursor: cursor.close()
        if cnx: cnx.close()
        return res

    def fetch(self, query: str, params: Tuple[Union[str, int, float]] = (), _all: bool = False) -> Optional[Dict[str, Union[str, int, float]]]:
        cnx = self.pool.get_connection()
        if not cnx:
            print('MySQL Error: Failed to retrieve a worker!')
            return None

        cursor = cnx.cursor(dictionary=True)
        cursor.execute(query, params)

        res = cursor.fetchall() if _all else cursor.fetchone()
        if cursor: cursor.close()
        if cnx: cnx.close()
        return res

    def fetchall(self, query: str, params: Tuple[Union[str, int, float]] = ()) -> Optional[Dict[str, Union[str, int, float]]]:
        return self.fetch(query, params, True)
