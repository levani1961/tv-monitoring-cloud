from pathlib import Path
from urllib.parse import urlparse
import re

from media_tools import DOWNLOADS_DIR, save_stream_duration
from stream_discovery import discover_hls_stream_url
from time_utils import hour_to_seconds


def _safe_filename(value):
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return value.strip("_")[:120] or "archive_video"


def download_archive_video(
    archive_url,
    archive_date,
    start_hour,
    end_hour,
    max_download_minutes=5,
    progress_hook=None,
):
    parsed = urlparse(archive_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("შეიყვანეთ სწორი Myvideo.ge არქივის ბმული.")

    DOWNLOADS_DIR.mkdir(exist_ok=True)

    requested_start_seconds = hour_to_seconds(start_hour)
    requested_end_seconds = hour_to_seconds(end_hour)
    if requested_end_seconds <= requested_start_seconds:
        raise ValueError("დასრულების საათი დაწყების საათზე გვიანი უნდა იყოს.")

    stream_url, stream_headers = discover_hls_stream_url(
        archive_url,
        wait_seconds=60,
        progress=progress_hook,
    )

    ranged_path = DOWNLOADS_DIR / (
        f"{_safe_filename(archive_date)}_{start_hour:02d}_{end_hour:02d}_range.mp4"
    )
    duration_seconds = requested_end_seconds - requested_start_seconds
    if max_download_minutes:
        duration_seconds = min(duration_seconds, int(max_download_minutes) * 60)

    save_stream_duration(
        stream_url,
        duration_seconds,
        ranged_path,
        input_headers=stream_headers,
    )
    return ranged_path
