from __future__ import annotations

from sqlalchemy import Column
from sqlalchemy import Index
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.dialects.mysql import ENUM
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.dialects.mysql import VARCHAR
from sqlalchemy.dialects.mysql import INTEGER

from app.repositories import Base


class ModMode(str):
    VANILLA = "vanilla"
    RELAX = "relax"
    AUTOPILOT = "autopilot"


class PerformanceReportsTable(Base):
    __tablename__ = "performance_reports"

    scoreid = Column(BIGINT(20), nullable=False, primary_key=True)
    mod_mode = Column(
        ENUM(ModMode),
        nullable=False,
        server_default=ModMode.VANILLA,
        primary_key=True,
    )
    os = Column(VARCHAR(length=64), nullable=False)
    fullscreen = Column(TINYINT(1), nullable=False)
    fps_cap = Column(VARCHAR(length=16), nullable=False)
    compatibility = Column(TINYINT(1), nullable=False)
    version = Column(VARCHAR(length=16), nullable=False)
    start_time = Column(INTEGER, nullable=False)
    end_time = Column(INTEGER, nullable=False)
    frame_count = Column(INTEGER, nullable=False)
    spike_frames = Column(INTEGER, nullable=False)
    aim_rate = Column(INTEGER, nullable=False)
    completion = Column(TINYINT(1), nullable=False)
    identifier = Column(VARCHAR(length=128), nullable=True)
    average_frametime = Column(INTEGER, nullable=False)
