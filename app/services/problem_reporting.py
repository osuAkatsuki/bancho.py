from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class ProblemReportingService:
    report_occurrence: Callable[[object], Awaitable[None]]

    async def report(self, occurrence: object) -> None:
        await self.report_occurrence(occurrence)
