from configparser import ConfigParser, Error as ConfigParserError
from pathlib import Path
import os


CONFIG_FILE = Path("config.ini")
ENV_FILE = Path(".env")


def _load_env_file():
    if not ENV_FILE.exists():
        return

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_settings():
    _load_env_file()

    parser = ConfigParser()
    if CONFIG_FILE.exists():
        try:
            parser.read(CONFIG_FILE, encoding="utf-8")
        except ConfigParserError as exc:
            raise ValueError(
                "config.ini არასწორად არის შევსებული."
            ) from exc

    # ვეძებთ გასაღებს რამდენიმე შესაძლო ადგილას მაქსიმალური თავსებადობისთვის
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        # ჯერ ვეძებთ [gemini] სექციაში
        gemini_key = parser.get("gemini", "api_key", fallback=None)
    if not gemini_key:
        # თუ იქ არ არის, ვეძებთ [google] სექციაში
        gemini_key = parser.get("google", "api_key", fallback=None)
    if not gemini_key:
        # ბოლო იმედი - იქნებ ისევ [openai] სექციაში წერია
        gemini_key = parser.get("openai", "api_key", fallback=None)

    return {
        "gemini_api_key": (gemini_key or "").strip(),
        "transcription_model": parser.get(
            "whisper", "model", fallback=parser.get("openai", "transcription_model", fallback="medium")
        ).strip(),
        "analysis_model": parser.get(
            "gemini", "analysis_model", fallback=parser.get("openai", "analysis_model", fallback="gemini-2.5-flash")
        ).strip(),
    }
