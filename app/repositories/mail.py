from __future__ import annotations

from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.mysql import TINYINT

import app.state.services
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


class Mail(TypedDict):
    id: int
    from_id: int
    to_id: int
    msg: str
    time: int
    read: bool


class MailWithUsernames(Mail):
    from_name: str
    to_name: str


async def create(from_id: int, to_id: int, msg: str) -> Mail:
    """Create a new mail entry in the database."""
    insert_stmt = insert(MailTable).values(
        from_id=from_id,
        to_id=to_id,
        msg=msg,
        time=func.unix_timestamp(),
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(MailTable.id == rec_id)
    mail = await app.state.services.database.fetch_one(select_stmt)
    assert mail is not None
    return cast(Mail, mail)


from app.repositories.users import UsersTable


async def fetch_all_mail_to_user(
    user_id: int,
    read: bool | None = None,
) -> list[MailWithUsernames]:
    """Fetch all of mail to a given target from the database."""
    from_subquery = select(UsersTable.name).where(UsersTable.id == MailTable.from_id)
    to_subquery = select(UsersTable.name).where(UsersTable.id == MailTable.to_id)

    select_stmt = select(
        *READ_PARAMS,
        from_subquery.label("from_name"),
        to_subquery.label("to_name"),
    ).where(MailTable.to_id == user_id)

    if read is not None:
        select_stmt = select_stmt.where(MailTable.read == read)

    mail = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[MailWithUsernames], mail)


async def mark_conversation_as_read(to_id: int, from_id: int) -> list[Mail]:
    """Mark any mail in a user's conversation with another user as read."""
    select_stmt = select(*READ_PARAMS).where(
        MailTable.to_id == to_id,
        MailTable.from_id == from_id,
        MailTable.read == False,
    )
    mail = await app.state.services.database.fetch_all(select_stmt)
    if not mail:
        return []

    update_stmt = (
        update(MailTable)
        .where(MailTable.to_id == to_id)
        .where(MailTable.from_id == from_id)
        .where(MailTable.read == False)
        .values(read=True)
    )
    await app.state.services.database.execute(update_stmt)
    return cast(list[Mail], mail)
