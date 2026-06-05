from pathlib import Path

from ai_analysis import analyze_hidden_ads
from media_tools import capture_screenshot, extract_violation_clip
from source_manager import cleanup_temporary_job
from transcription import transcribe_video


def process_video_jobs(
    client,
    jobs,
    transcription_model,
    analysis_model,
    progress=None,
):
    all_violations = []
    analysis_metadata = []

    for job_index, job in enumerate(jobs, start=1):
        if progress:
            progress(f"{job_index}/{len(jobs)} | ტრანსკრიპცია: {Path(job.video_path).name}")

        try:
            segments = transcribe_video(
                client=client,
                video_path=job.video_path,
                model_name=transcription_model,
                language="ka",
                progress=progress,
            )

            if progress:
                progress(f"{job_index}/{len(jobs)} | ჟანრის და რეკლამის AI ანალიზი...")

            violations, metadata = analyze_hidden_ads(
                client=client,
                segments=segments,
                model_name=analysis_model,
                channel=job.channel,
                broadcast_date=job.broadcast_start.strftime("%Y-%m-%d"),
                progress=progress,
            )
            analysis_metadata.append(metadata)

            if violations and progress:
                progress(f"{job_index}/{len(jobs)} | სამართლებრივი მტკიცებულებების შექმნა...")

            for local_index, violation in enumerate(violations, start=1):
                violation.clip_path = str(
                    extract_violation_clip(
                        job.video_path,
                        violation,
                        local_index,
                        job.broadcast_start,
                    )
                )
                violation.screenshot_path = str(
                    capture_screenshot(job.video_path, violation, local_index, job.broadcast_start)
                )

            all_violations.extend(violations)
        finally:
            cleanup_temporary_job(job)

    return all_violations, analysis_metadata
