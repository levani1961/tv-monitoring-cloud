from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class Violation:
    start: float
    end: float
    transcript: str
    brand_name: str
    probability_score: int
    risk_status: str
    reason: str
    channel: str = ""
    broadcast_date: str = ""
    genre: str = ""
    clip_path: str = ""
    screenshot_path: str = ""


@dataclass
class VideoJob:
    source_type: str
    channel: str
    broadcast_start: datetime
    video_path: Path
    is_temporary: bool = False
    source_url: str = ""
