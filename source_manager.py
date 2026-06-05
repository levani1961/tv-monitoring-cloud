from datetime import date, datetime, time, timedelta
from pathlib import Path

from media_tools import DOWNLOADS_DIR, save_stream_duration
from models import VideoJob
from stream_discovery import discover_hls_stream_url
from time_utils import hour_to_seconds


CHANNELS = [
    "იმედი",
    "რუსთავი 2",
    "მთავარი არხი",
    "ფორმულა",
    "პირველი არხი",
    "პოსტვ",
    "აჭარა TV",
    "სხვა",
]

LOCAL_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".ts", ".m4v"}


def iter_dates(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def build_archive_url(url_template, channel, archive_date, hour):
    if not url_template:
        raise ValueError("Myvideo.ge URL ან URL შაბლონი აუცილებელია.")

    return url_template.format(
        channel=channel,
        date=archive_date.isoformat(),
        hour=f"{hour:02d}",
    )


def create_myvideo_jobs(
    channel,
    start_date,
    end_date,
    start_hour,
    end_hour,
    url_template,
    max_chunk_minutes,
    visible_browser=False,
    progress=None,
):
    if end_date < start_date:
        raise ValueError("დასრულების თარიღი დაწყების თარიღზე ადრე ვერ იქნება.")
    if end_hour <= start_hour:
        raise ValueError("დასრულების საათი დაწყების საათზე გვიანი უნდა იყოს.")

    jobs = []
    DOWNLOADS_DIR.mkdir(exist_ok=True)

    for archive_date in iter_dates(start_date, end_date):
        for hour in range(int(start_hour), int(end_hour)):
            page_url = build_archive_url(url_template, channel, archive_date, hour)
            broadcast_start = datetime.combine(archive_date, time(hour=hour))

            if progress:
                progress(f"{channel} | {archive_date} {hour:02d}:00 - ნაკადის ძებნა...")

            stream_url, headers = discover_hls_stream_url(
                page_url,
                wait_seconds=90 if visible_browser else 60,
                headless=not visible_browser,
                progress=progress,
            )
            duration_seconds = min(3600, int(max_chunk_minutes) * 60)
            output_path = DOWNLOADS_DIR / f"{channel}_{archive_date}_{hour:02d}_chunk.mp4"

            if progress:
                progress(f"{channel} | {archive_date} {hour:02d}:00 - სამუშაო მონაკვეთის შექმნა...")

            save_stream_duration(stream_url, duration_seconds, output_path, input_headers=headers)
            jobs.append(
                VideoJob(
                    source_type="myvideo",
                    channel=channel,
                    broadcast_start=broadcast_start,
                    video_path=output_path,
                    is_temporary=True,
                    source_url=page_url,
                )
            )

    return jobs


def create_local_jobs(local_directory, channel, broadcast_date, start_hour):
    folder = Path(local_directory)
    if not folder.exists() or not folder.is_dir():
        raise ValueError("მითითებული ლოკალური საქაღალდე ვერ მოიძებნა.")

    files = sorted(
        path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in LOCAL_VIDEO_EXTENSIONS
    )
    if not files:
        raise ValueError("საქაღალდეში ვიდეო ფაილები ვერ მოიძებნა.")

    broadcast_start = datetime.combine(broadcast_date, time(hour=int(start_hour)))
    return [
        VideoJob(
            source_type="local",
            channel=channel,
            broadcast_start=broadcast_start,
            video_path=path,
            is_temporary=False,
        )
        for path in files
    ]


def cleanup_temporary_job(job):
    if not job.is_temporary:
        return

    try:
        Path(job.video_path).unlink(missing_ok=True)
    except PermissionError:
        pass
