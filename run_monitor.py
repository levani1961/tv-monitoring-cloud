import sys
from datetime import date, datetime
from pathlib import Path

# === პარამეტრები - შეცვალეთ აქ ===
CHANNELS = ['imedi', 'rustavi2'] # არხების სია
TARGET_DATE = '2026-06-04'       # თარიღი (YYYY-MM-DD)
START_HOUR = 8                   # საწყისი საათი
END_HOUR = 11                    # დასრულების საათი (ამ საათის ჩათვლით არ მოხდება)
MINUTES_PER_HOUR = 60            # რამდენი წუთი გაანალიზდეს ყოველი საათიდან (60 = მთლიანი საათი)

# Myvideo URL შაბლონი (თუ Myvideo-ს იყენებთ)
# შაბლონში {channel}, {date} და {hour} ავტომატურად შეივსება
MYVIDEO_URL_TEMPLATE = "https://www.myvideo.ge/tv/{channel}/{date}/{hour}"
# =================================

# იმპორტები პროექტის მოდულებიდან
from config import load_settings
from processing import process_video_jobs
from source_manager import create_myvideo_jobs
from excel_report import build_excel_report
from media_tools import ensure_media_dirs

def terminal_progress(message):
    """ბეჭდავს პროგრესს ტერმინალში დროის მითითებით"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def run_cli_monitoring():
    print("="*60)
    print("Enterprise AI ტელემონიტორინგი - ავტომატური CLI რეჟიმი")
    print("="*60)
    print(f"თარიღი: {TARGET_DATE}")
    print(f"არხები: {', '.join(CHANNELS)}")
    print(f"პერიოდი: {START_HOUR}:00 - {END_HOUR}:00")
    print("="*60)

    # 1. პარამეტრების მომზადება
    settings = load_settings()
    ensure_media_dirs()

    gemini_key = settings.get("gemini_api_key")
    if not gemini_key or "აქ_ჩავსვამ" in gemini_key or "your_gemini" in gemini_key:
        print(f"შეცდომა: Gemini API key არ არის მითითებული config.ini-ში! (ნაპოვნია: {gemini_key})")
        return

    try:
        analysis_date = date.fromisoformat(TARGET_DATE)
    except ValueError:
        print(f"შეცდომა: TARGET_DATE ფორმატი არასწორია ({TARGET_DATE}). გამოიყენეთ YYYY-MM-DD.")
        return

    all_violations = []
    all_metadata = []

    # 2. ციკლი არხების მიხედვით
    for channel_id in CHANNELS:
        terminal_progress(f"--- იწყება არხის დამუშავება: {channel_id} ---")
        
        try:
            terminal_progress(f"ვიდეოების მომზადება Myvideo არქივიდან...")
            jobs = create_myvideo_jobs(
                channel=channel_id,
                start_date=analysis_date,
                end_date=analysis_date,
                start_hour=START_HOUR,
                end_hour=END_HOUR,
                url_template=MYVIDEO_URL_TEMPLATE,
                max_chunk_minutes=MINUTES_PER_HOUR,
                progress=terminal_progress
            )

            if not jobs:
                terminal_progress(f"გაფრთხილება: {channel_id}-სთვის ვიდეოები ვერ მოიძებნა.")
                continue

            terminal_progress(f"იწყება ანალიზი ({len(jobs)} მონაკვეთი)...")
            violations, metadata_list = process_video_jobs(
                gemini_key=gemini_key,
                jobs=jobs,
                transcription_model=settings["transcription_model"],
                analysis_model=settings["analysis_model"],
                progress=terminal_progress
            )
            
            all_violations.extend(violations)
            all_metadata.extend(metadata_list)
            
            terminal_progress(f"არხი {channel_id} დასრულდა. ნაპოვნია {len(violations)} დარღვევა.")

        except Exception as e:
            terminal_progress(f"შეცდომა {channel_id}-ს დამუშავებისას: {str(e)}")
            continue

    if not all_violations and not all_metadata:
        print("\nდამუშავებული მონაცემები არ არის.")
        return

    # 3. საერთო Excel ანგარიშის შექმნა
    terminal_progress("ყველა არხი დასრულდა. საერთო Excel ანგარიშის მომზადება...")
    
    report_metadata = {
        "channel": ", ".join(CHANNELS),
        "date_range": TARGET_DATE,
        "genre": ", ".join(sorted({item.get("content_genre", "") for item in all_metadata if item.get("content_genre")})),
        "ignored_reason": "; ".join(set(item.get("ignored_reason", "") for item in all_metadata if item.get("ignored_reason"))),
    }

    report_path = build_excel_report(all_violations, metadata=report_metadata)
    
    print("\n" + "="*60)
    print(f"მონიტორინგი დასრულდა!")
    print(f"ჯამში ნაპოვნია {len(all_violations)} სავარაუდო დარღვევა.")
    print(f"საბოლოო ანგარიში: {report_path}")
    print("="*60)

if __name__ == "__main__":
    try:
        run_cli_monitoring()
    except KeyboardInterrupt:
        print("\nპროცესი შეწყვეტილია მომხმარებლის მიერ.")
    except Exception as e:
        import traceback
        print(f"\nკრიტიკული შეცდომა:\n{traceback.format_exc()}")
