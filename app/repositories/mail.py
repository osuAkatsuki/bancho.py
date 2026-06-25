from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.mysql import TINYINT

from app.adapters.database import Database
from app.adapters.database import MySQLRow
from app.repositories import Base


class MailTable(Base):
    __tablename__ = "mail"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    from_id = Column("from_id", Integer, nullable=False)
    to_id = Column("to_id", Integer, nullable=False)
    msg = Column("msg", String(2048, collation="utf8"), nullable=False)
    time = Column("time", Integer, nullable=True)
    read = Column("read", TINYINT(1), nullable=False, server_default="0")


READ_PARAMS = (
    MailTable.id,
    MailTable.from_id,
    MailTable.to_id,
    MailTable.msg,
    MailTable.time,
    MailTable.read,
)


@dataclass(frozen=True, slots=True)
class Mail:
    id: int
    from_id: int
    to_id: int
    msg: str
    time: int
    read: bool


@dataclass(frozen=True, slots=True)
class MailWithUsernames:
    id: int
    from_id: int
    to_id: int
    msg: str
    time: int
    read: bool
    from_name: str
    to_name: str


from app.repositories.users import UsersTable


class MailRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def _serialize_mail(self, mail: Mail) -> MySQLRow:
        return {
            "id": mail.id,
            "from_id": mail.from_id,
            "to_id": mail.to_id,
            "msg": mail.msg,
            "time": mail.time,
            "read": mail.read,
        }

    def _deserialize_mail(self, row: MySQLRow) -> Mail:
        return Mail(
            id=row["id"],
            from_id=row["from_id"],
            to_id=row["to_id"],
            msg=row["msg"],
            time=row["time"],
            read=bool(row["read"]),
        )

    def _serialize_mail_with_usernames(self, mail: MailWithUsernames) -> MySQLRow:
        return {
            "id": mail.id,
            "from_id": mail.from_id,
            "to_id": mail.to_id,
            "msg": mail.msg,
            "time": mail.time,
            "read": mail.read,
            "from_name": mail.from_name,
            "to_name": mail.to_name,
        }

    def _deserialize_mail_with_usernames(self, row: MySQLRow) -> MailWithUsernames:
        return MailWithUsernames(
            id=row["id"],
            from_id=row["from_id"],
            to_id=row["to_id"],
            msg=row["msg"],
            time=row["time"],
            read=bool(row["read"]),
            from_name=row["from_name"],
            to_name=row["to_name"],
        )

    async def create(self, from_id: int, to_id: int, msg: str) -> Mail:
        """Create a new mail entry in the database."""
        insert_stmt = insert(MailTable).values(
            from_id=from_id,
            to_id=to_id,
            msg=msg,
            time=func.unix_timestamp(),
        )
        rec_id = await self._database.execute(insert_stmt)

        select_stmt = select(*READ_PARAMS).where(MailTable.id == rec_id)
        mail = await self._database.fetch_one(select_stmt)
        assert mail is not None
        return self._deserialize_mail(mail)

    async def fetch_all_mail_to_user(
        self,
        user_id: int,
        read: bool | None = None,
    ) -> list[MailWithUsernames]:
        """Fetch all of mail to a given target from the database."""
        from_subquery = select(UsersTable.name).where(
            UsersTable.id == MailTable.from_id,
        )
        to_subquery = select(UsersTable.name).where(UsersTable.id == MailTable.to_id)

        select_stmt = select(
            *READ_PARAMS,
            from_subquery.label("from_name"),
            to_subquery.label("to_name"),
        ).where(MailTable.to_id == user_id)

        if read is not None:
            select_stmt = select_stmt.where(MailTable.read == read)

        mail = await self._database.fetch_all(select_stmt)
        return [self._deserialize_mail_with_usernames(row) for row in mail]

    async def mark_conversation_as_read(self, to_id: int, from_id: int) -> list[Mail]:
        """Mark any mail in a user's conversation with another user as read."""
        select_stmt = select(*READ_PARAMS).where(
            MailTable.to_id == to_id,
            MailTable.from_id == from_id,
            MailTable.read == False,
        )
        mail = await self._database.fetch_all(select_stmt)
        if not mail:
            return []

        update_stmt = (
            update(MailTable)
            .where(MailTable.to_id == to_id)
            .where(MailTable.from_id == from_id)
            .where(MailTable.read == False)
            .values(read=True)
        )
        await self._database.execute(update_stmt)
        return [self._deserialize_mail(row) for row in mail]
