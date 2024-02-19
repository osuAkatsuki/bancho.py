from __future__ import annotations

from sqlalchemy.dialects import mysql
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class MySQLDialect(mysql.dialect):
    default_paramstyle = "named"


DIALECT = MySQLDialect()
