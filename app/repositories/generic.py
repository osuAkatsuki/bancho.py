from __future__ import annotations

from typing import Any
from typing import Optional

import app.state.services


class GenericRepository:
    def __init__(self, table_name: str, read_params: str):
        self.table_name = table_name
        self.read_params = read_params

    async def create(self, **kwargs) -> dict[str, Any]:
        query_params = ", ".join(kwargs.keys())
        query_values = ", ".join([f":{key}" for key in kwargs.keys()])
        query = f"""
            INSERT INTO {self.table_name} ({query_params})
                 VALUES ({query_values})
        """

        rec_id = await app.state.services.database.execute(query, kwargs)

        query = f"""\
            SELECT {self.read_params}
              FROM {self.table_name}
             WHERE id = :id
        """
        params = {
            "id": rec_id,
        }

        rec = await app.state.services.database.fetch_one(query, params)
        assert rec is not None
        return dict(rec)

    async def fetch_one(self, **kwargs):
        pass

    async def fetch_many(self, **kwargs):
        pass

    async def fetch_count(self, **kwargs):
        pass

    async def update(self, id, **kwargs):
        pass
