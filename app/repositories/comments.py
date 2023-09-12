from __future__ import annotations

import textwrap
from typing import Any
from typing import Optional

import app.state.services
from app.repositories.generic import GenericRepository


READ_PARAMS = textwrap.dedent(
    """\
        id, target_id, target_type, userid, time, comment, colour
    """,
)


class CommentsRepository(GenericRepository):
    def __init__(self):
        super().__init__("comments", READ_PARAMS)

    # Define any specific methods here
