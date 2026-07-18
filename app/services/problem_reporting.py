from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable
from typing import Callable


@dataclass(frozen=True)
class ProblemReportingService:
    report_occurrence: Callable[[object], Awaitable[None]]

    async def report(self, occurrence: object) -> None:
        await self.report_occurrence(occurrence)
