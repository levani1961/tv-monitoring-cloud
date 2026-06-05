from datetime import date
from pathlib import Path

import streamlit as st
import os
if not os.path.exists("/opt/render/.cache/ms-playwright"):
    os.system("playwright install chromium")

st.session_state["logged_in"] = True


from config import load_settings
from excel_report import build_excel_report, violation_rows_for_dashboard
from license_guard import LICENSE_EXPIRED_MESSAGE, check_license
from media_tools import ensure_media_dirs
from processing import process_video_jobs
from source_manager import CHANNELS, create_local_jobs, create_myvideo_jobs


st.set_page_config(page_title="Enterprise AI ტელემონიტორინგი", layout="wide")

def check_password():
    """აბრუნებს True-ს, თუ მომხმარებელმა შეიყვანა სწორი პაროლი."""

    def password_entered():
        """ამოწმებს პაროლის სისწორეს."""
        if st.session_state["username"] == "" and st.session_state["password"] == "":
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # პაროლი აღარ გვჭირდება სესიაში
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # პირველი გაშვება, აჩვენებს ავტორიზაციის ფორმას
        st.title("ავტორიზაცია")
        st.text_input("მომხმარებელი", key="username")
        st.text_input("პაროლი", type="password", key="password")
        st.button("შესვლა", on_click=password_entered)
        return False
    elif not st.session_state["password_correct"]:
        # არასწორი პაროლი, აჩვენებს ფორმას და შეცდომას
        st.title("ავტორიზაცია")
        st.text_input("მომხმარებელი", key="username")
        st.text_input("პაროლი", type="password", key="password")
        st.button("შესვლა", on_click=password_entered)
        st.error("❌ მომხმარებლის სახელი ან პაროლი არასწორია")
        return False
    else:
        # სწორი პაროლი
        return True

def stop_if_unlicensed():
    try:
        check_license()
    except PermissionError:
        st.error(LICENSE_EXPIRED_MESSAGE)
        st.stop()


def channel_selector():
    selected = st.selectbox("TV არხი", CHANNELS, index=0)
    if selected == "სხვა":
        return st.text_input("არხის სახელი", value="Unknown Channel")
    return selected


def render_sidebar(settings):
    with st.sidebar:
        st.subheader("სისტემის პარამეტრები")
        transcription_model = st.text_input(
            "ტრანსკრიპციის მოდელი (Gemini Audio)",
            value=settings["analysis_model"],
            help="ტრანსკრიპციისთვისაც გამოყენებული იქნება Gemini, რათა სერვერი არ დაიტვირთოს.",
            disabled=True
        )
        analysis_model = st.text_input(
            "AI ანალიზის მოდელი (Gemini)", 
            value=settings["analysis_model"],
            help="Gemini მოდელი: gemini-2.5-flash ან gemini-2.5-pro",
        )
        st.caption("API key ინახება მხოლოდ config.ini/.env-ში და არ იწერება კოდში.")
    return transcription_model, analysis_model


def build_jobs_from_ui(source_type):
    if source_type == "Myvideo.ge Archive":
        st.subheader("Source A: Myvideo.ge არქივი")
        channel = channel_selector()

        archive_date = st.date_input("ეთერის თარიღი", value=date.today())

        col1, col2 = st.columns(2)
        with col1:
            start_hour = st.number_input("დაწყების საათი", min_value=0, max_value=23, value=8)
        with col2:
            end_hour = st.number_input("დასრულების საათი", min_value=1, max_value=24, value=9)

        max_chunk_minutes = st.number_input(
            "თითო საათიდან დამუშავებული წუთები",
            min_value=1,
            max_value=60,
            value=5,
            help="ტესტირებისას დატოვეთ 5 წუთი. production რეჟიმში დააყენეთ 60.",
        )

        archive_url_template = st.text_input(
            "Myvideo.ge ზუსტი არქივის/player URL",
            help="ჩასვით ზუსტად ის URL, რომელიც ადრე მუშაობდა და სადაც ვიდეო player იხსნება.",
        )

        return {
            "kind": "myvideo",
            "channel": channel,
            "start_date": archive_date,
            "end_date": archive_date,
            "start_hour": int(start_hour),
            "end_hour": int(end_hour),
            "max_chunk_minutes": int(max_chunk_minutes),
            "visible_browser": False,
            "archive_url_template": archive_url_template,
        }

    st.subheader("Source B: Local Disk / Flash Drive / Disc")
    channel = channel_selector()
    local_directory = st.text_input("ვიდეოების საქაღალდის სრული მისამართი")

    col1, col2 = st.columns(2)
    with col1:
        broadcast_date = st.date_input("ეთერის თარიღი", value=date.today())
    with col2:
        start_hour = st.number_input("პირველი ფაილის საწყისი საათი", min_value=0, max_value=23, value=8)

    return {
        "kind": "local",
        "channel": channel,
        "local_directory": local_directory,
        "broadcast_date": broadcast_date,
        "start_hour": int(start_hour),
    }


def materialize_jobs(options, progress):
    if options["kind"] == "myvideo":
        return create_myvideo_jobs(
            channel=options["channel"],
            start_date=options["start_date"],
            end_date=options["end_date"],
            start_hour=options["start_hour"],
            end_hour=options["end_hour"],
            url_template=options["archive_url_template"],
            max_chunk_minutes=options["max_chunk_minutes"],
            visible_browser=options["visible_browser"],
            progress=progress,
        )

    return create_local_jobs(
        local_directory=options["local_directory"],
        channel=options["channel"],
        broadcast_date=options["broadcast_date"],
        start_hour=options["start_hour"],
    )


def render_results(violations, report_path):
    if not violations:
        st.info("დარღვევა ვერ მოიძებნა.")
    else:
        st.subheader("გაფილტრული შედეგები")
        st.dataframe(violation_rows_for_dashboard(violations), use_container_width=True)

        st.subheader("ვიდეო მტკიცებულებები")
        for index, violation in enumerate(violations, start=1):
            with st.expander(
                f"{index}. {violation.channel} | {violation.broadcast_date} | "
                f"{violation.risk_status} | {violation.probability_score}%",
                expanded=index == 1,
            ):
                st.write(f"**ბრენდი/ობიექტი:** {violation.brand_name}")
                st.write(f"**AI მიზეზი:** {violation.reason}")
                st.write(violation.transcript)

                if violation.clip_path and Path(violation.clip_path).exists():
                    st.video(violation.clip_path)
                    with Path(violation.clip_path).open("rb") as clip_file:
                        st.download_button(
                            "MP4 მტკიცებულების ჩამოტვირთვა",
                            clip_file,
                            file_name=Path(violation.clip_path).name,
                            mime="video/mp4",
                            key=f"clip_{index}",
                        )

    with Path(report_path).open("rb") as report_file:
        st.download_button(
            "Excel ანგარიშის ჩამოტვირთვა",
            report_file,
            file_name=Path(report_path).name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )


def main():
    if not check_password():
        st.stop()

    stop_if_unlicensed()
    ensure_media_dirs()

    settings = load_settings()
    # ვამოწმებთ, რომ გასაღები არსებობს და არ არის ცარიელი ან სატესტო ტექსტი
    gemini_key = settings.get("gemini_api_key", "")
    if not gemini_key or "აქ_ჩავსვამ" in gemini_key or "your_gemini" in gemini_key:
        st.error("Gemini API key არ არის მითითებული. გთხოვთ, ჩაწეროთ თქვენი API გასაღები config.ini ფაილში [gemini] სექციის ქვეშ.")
        st.info("ამჟამინდელი მნიშვნელობა config.ini-ში: " + (gemini_key if gemini_key else "ცარიელია"))
        st.stop()

    transcription_model, analysis_model = render_sidebar(settings)

    st.title("Enterprise AI ტელემონიტორინგი")
    st.caption("ფარული რეკლამის სამართლებრივი მონიტორინგი ჟანრის მკაცრი ფილტრით")

    source_type = st.radio(
        "მონაცემის წყარო",
        ["Myvideo.ge Archive", "Local Disk / Flash Drive / Disc"],
        horizontal=True,
    )
    options = build_jobs_from_ui(source_type)

    if not st.button("მონიტორინგის დაწყება", type="primary"):
        return

    status = st.empty()

    def progress(message):
        status.info(message)

    try:
        progress("სამუშაო ვიდეოების მომზადება...")
        jobs = materialize_jobs(options, progress)

        if not jobs:
            st.warning("დასამუშავებელი ვიდეო ვერ მოიძებნა.")
            return

        violations, metadata = process_video_jobs(
            gemini_key=settings.get("gemini_api_key"),
            jobs=jobs,
            transcription_model=transcription_model,
            analysis_model=analysis_model,
            progress=progress,
        )

        report_metadata = {
            "channel": options.get("channel", "-"),
            "date_range": f"{options.get('start_date', options.get('broadcast_date'))} - {options.get('end_date', options.get('broadcast_date'))}",
            "genre": ", ".join(sorted({item.get("content_genre", "") for item in metadata if item.get("content_genre")})),
            "ignored_reason": "; ".join(item.get("ignored_reason", "") for item in metadata if item.get("ignored_reason")),
        }

        progress("Excel ანგარიშის შექმნა...")
        report_path = build_excel_report(violations, metadata=report_metadata)

        status.success("დასრულდა.")
        render_results(violations, report_path)

    except Exception as exc:
        st.error(str(exc))


if __name__ == "__main__":
    main()
