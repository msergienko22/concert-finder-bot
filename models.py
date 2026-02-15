"""
Shared data models: Event and Source.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class Source(str, Enum):
    TICKETMASTER = "ticketmaster"
    PARADISO = "paradiso"
    MELKWEG = "melkweg"
    AFAS_LIVE = "afaslive"
    ZIGGO_DOME = "ziggodome"


@dataclass
class Event:
    source: Source
    title: str
    venue: str
    date_raw: str
    date_normalized: str  # YYYY-MM-DD or TBA
    url: str
    status: Optional[str] = None
    fetched_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.fetched_at is None:
            self.fetched_at = datetime.utcnow()
