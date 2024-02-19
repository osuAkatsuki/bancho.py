from __future__ import annotations

from typing import Any

from sqlalchemy.dialects.mysql.mysqldb import MySQLDialect_mysqldb
from sqlalchemy.orm import declarative_base

Base: Any = declarative_base()


class MySQLDialect(MySQLDialect_mysqldb):
    default_paramstyle = "named"


DIALECT = MySQLDialect()
