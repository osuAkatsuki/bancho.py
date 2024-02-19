from __future__ import annotations

from sqlalchemy.dialects.mysql.mysqldb import MySQLDialect_mysqldb
from sqlalchemy.orm import DeclarativeMeta
from sqlalchemy.orm import registry

mapper_registry = registry()


class Base(metaclass=DeclarativeMeta):
    __abstract__ = True

    registry = mapper_registry
    metadata = mapper_registry.metadata

    __init__ = mapper_registry.constructor


class MySQLDialect(MySQLDialect_mysqldb):
    default_paramstyle = "named"


DIALECT = MySQLDialect()
