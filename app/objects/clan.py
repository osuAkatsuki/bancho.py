from __future__ import annotations

from datetime import datetime

__all__ = ("Clan",)


class Clan:
    """A class to represent a single bancho.py clan."""

    def __init__(
        self,
        id: int,
        name: str,
        tag: str,
        created_at: datetime,
        owner_id: int,
        member_ids: set[int],
    ) -> None:
        """A class representing one of bancho.py's clans."""
        self.id = id
        self.name = name
        self.tag = tag
        self.created_at = created_at

        self.owner_id = owner_id  # userid
        self.member_ids = member_ids  # userids

    def __repr__(self) -> str:
        return f"[{self.tag}] {self.name}"
