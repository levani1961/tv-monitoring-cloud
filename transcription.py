from pathlib import Path
from time import sleep

from openai import OpenAI
from openai import BadRequestError

from media_tools import TEMP_DIR, extract_audio_chunk
from models import TranscriptSegment


CHUNK_SECONDS = 10 * 60


def _safe_unlink(path):
    for _ in range(5):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            sleep(0.5)


def _response_text(response):
    if isinstance(response, str):
        return response.strip()
    return (getattr(response, "text", "") or "").strip()


def _append_response_segments(segments, response, chunk_index, duration_seconds):
    api_segments = getattr(response, "segments", None) or []
    if api_segments:
        for item in api_segments:
            text = getattr(item, "text", "").strip()
            if not text:
                continue
            segments.append(
                TranscriptSegment(
                    start=float(getattr(item, "start", 0)) + chunk_index,
                    end=float(getattr(item, "end", 0)) + chunk_index,
                    text=text,
                )
            )
        return

    text = _response_text(response)
    if text:
        segments.append(
            TranscriptSegment(
                start=float(chunk_index),
                end=float(chunk_index + duration_seconds),
                text=text,
            )
        )


def transcribe_video(client: OpenAI, video_path, model_name, language="ka", progress=None):
    video_path = Path(video_path)
    TEMP_DIR.mkdir(exist_ok=True)
    segments = []

    # We process generously sized chunks so the API upload remains manageable.
    for chunk_index in range(0, 24 * 60 * 60, CHUNK_SECONDS):
        audio_path = TEMP_DIR / f"{video_path.stem}_{chunk_index}.m4a"

        try:
            extract_audio_chunk(video_path, chunk_index, CHUNK_SECONDS, audio_path)
        except Exception:
            break

        if audio_path.stat().st_size < 1024:
            audio_path.unlink(missing_ok=True)
            break

        if progress:
            progress(f"ტრანსკრიპცია: {chunk_index // 60} წუთიდან...")

        duration_for_segment = CHUNK_SECONDS
        with audio_path.open("rb") as audio_file:
            try:
                response = client.audio.transcriptions.create(
                    model=model_name,
                    file=audio_file,
                    language=language,
                    prompt="ეს არის ქართული სატელევიზიო გადაცემის აუდიო. ტექსტი გადაწერე ქართულად.",
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )
            except BadRequestError as exc:
                error_text = str(exc)

                if "unsupported_value" in error_text or "response_format" in error_text:
                    if progress:
                        progress(
                            "ეს მოდელი timestamp JSON-ს არ აბრუნებს; ვიღებ სუფთა ქართულ ტექსტს..."
                        )

                    audio_file.seek(0)
                    response = client.audio.transcriptions.create(
                        model=model_name,
                        file=audio_file,
                        prompt="ეს არის ქართული სატელევიზიო გადაცემის აუდიო. ტექსტი გადაწერე ქართულად.",
                        response_format="json",
                    )
                    _append_response_segments(
                        segments,
                        response,
                        chunk_index,
                        duration_for_segment,
                    )
                    _safe_unlink(audio_path)
                    continue

                if "unsupported_language" not in error_text:
                    raise

                if progress:
                    progress(
                        "API-მ ქართული ენის კოდი არ მიიღო; ტრანსკრიპცია გრძელდება ავტომატური ენის ამოცნობით..."
                    )

                audio_file.seek(0)
                response = client.audio.transcriptions.create(
                    model=model_name,
                    file=audio_file,
                    prompt="ეს არის ქართული სატელევიზიო გადაცემის აუდიო. ტექსტი გადაწერე ქართულად.",
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )

        _append_response_segments(segments, response, chunk_index, duration_for_segment)

        _safe_unlink(audio_path)

    return segments
