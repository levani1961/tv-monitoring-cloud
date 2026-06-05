from pathlib import Path
from datetime import timedelta
import subprocess
import re


DOWNLOADS_DIR = Path("downloads")
EXTRACTED_CLIPS_DIR = Path("extracted_clips")
SCREENSHOTS_DIR = Path("screenshots")
TEMP_DIR = Path("temp_audio")


def ensure_media_dirs():
    for folder in [DOWNLOADS_DIR, EXTRACTED_CLIPS_DIR, SCREENSHOTS_DIR, TEMP_DIR]:
        folder.mkdir(exist_ok=True)

    for temp_file in TEMP_DIR.glob("*.m4a"):
        try:
            temp_file.unlink()
        except PermissionError:
            pass


def run_ffmpeg(command, timeout_seconds=900):
    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("FFmpeg ძალიან დიდხანს მუშაობს და შეჩერდა.") from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or "").strip()
        if len(message) > 1200:
            message = message[-1200:]
        raise RuntimeError(f"FFmpeg შეცდომა: {message}") from exc


def _ffmpeg_header_args(input_headers):
    if not input_headers:
        return []

    header_lines = "".join(f"{key}: {value}\r\n" for key, value in input_headers.items())
    return ["-headers", header_lines]


def _safe_filename(value):
    value = re.sub(r"[^A-Za-z0-9ა-ჰ_.-]+", "_", value, flags=re.UNICODE)
    return value.strip("_") or "Unknown"


def _drawtext_escape(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
    )


def _ffmpeg_fontfile():
    candidates = [
        Path("C:/Windows/Fonts/sylfaen.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate).replace("\\", "/").replace(":", "\\:")
    return ""


def cut_video_range(input_video, start_seconds, end_seconds, output_path, input_headers=None):
    duration = max(1, end_seconds - start_seconds)
    command = [
        "ffmpeg",
        "-y",
        *_ffmpeg_header_args(input_headers),
        "-ss",
        str(max(0, start_seconds)),
        "-i",
        str(input_video),
        "-t",
        str(duration),
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    run_ffmpeg(command)
    return output_path


def save_stream_duration(input_url, duration_seconds, output_path, input_headers=None):
    command = [
        "ffmpeg",
        "-y",
        *_ffmpeg_header_args(input_headers),
        "-i",
        str(input_url),
        "-t",
        str(max(1, int(duration_seconds))),
        "-c",
        "copy",
        "-bsf:a",
        "aac_adtstoasc",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    run_ffmpeg(command)
    return output_path


def extract_audio_chunk(input_video, start_seconds, duration_seconds, output_path):
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        str(max(0, start_seconds)),
        "-i",
        str(input_video),
        "-t",
        str(duration_seconds),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "64k",
        str(output_path),
    ]
    run_ffmpeg(command)
    return output_path


def extract_violation_clip(input_video, violation, index, broadcast_start):
    clip_start = max(0, violation.start)
    duration = max(1, violation.end - violation.start)
    date_part = broadcast_start.strftime("%Y-%m-%d")
    time_part = (broadcast_start + timedelta(seconds=int(violation.start))).strftime("%H-%M-%S")
    channel = _safe_filename(violation.channel)
    output_path = EXTRACTED_CLIPS_DIR / f"{channel}_{date_part}_{time_part}_Hidden_Ad.mp4"

    burn_time = (broadcast_start + timedelta(seconds=int(violation.start))).strftime("%Y-%m-%d %H:%M:%S")
    overlay_text = _drawtext_escape(f"{violation.channel} | {burn_time}")
    fontfile = _ffmpeg_fontfile()
    font_part = f"fontfile='{fontfile}':" if fontfile else ""
    drawtext = (
        "drawtext="
        + font_part
        + "text='"
        + overlay_text
        + "':x=20:y=20:fontsize=28:fontcolor=white:"
        + "box=1:boxcolor=black@0.65:boxborderw=10"
    )

    command = [
        "ffmpeg",
        "-y",
        "-ss",
        str(clip_start),
        "-i",
        str(input_video),
        "-t",
        str(duration),
        "-vf",
        drawtext,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    try:
        run_ffmpeg(command)
    except RuntimeError as exc:
        if "Fontconfig" not in str(exc) and "drawtext" not in str(exc):
            raise

        fallback_command = [
            "ffmpeg",
            "-y",
            "-ss",
            str(clip_start),
            "-i",
            str(input_video),
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        run_ffmpeg(fallback_command)
    return output_path


def capture_screenshot(input_video, violation, index, broadcast_start=None):
    screenshot_second = max(0, (violation.start + violation.end) / 2)
    if broadcast_start:
        date_part = broadcast_start.strftime("%Y-%m-%d")
        time_part = (broadcast_start + timedelta(seconds=int(violation.start))).strftime("%H-%M-%S")
        output_path = SCREENSHOTS_DIR / (
            f"{_safe_filename(violation.channel)}_{date_part}_{time_part}_Hidden_Ad.jpg"
        )
    else:
        output_path = SCREENSHOTS_DIR / f"violation_{index:04d}_{int(violation.start)}.jpg"
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        str(screenshot_second),
        "-i",
        str(input_video),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output_path),
    ]
    run_ffmpeg(command)
    return output_path
