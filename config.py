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
                "config.ini არასწორად არის შევსებული. გამოიყენეთ ფორმა: "
                "[openai] შემდეგ api_key = თქვენი_გასაღები"
            ) from exc

    return {
        "openai_api_key": os.getenv("OPENAI_API_KEY")
        or parser.get("openai", "api_key", fallback="").strip(),
        "transcription_model": parser.get(
            "openai", "transcription_model", fallback="gpt-4o-transcribe"
        ).strip(),
        "analysis_model": parser.get(
            "openai", "analysis_model", fallback="gpt-4o-mini"
        ).strip(),
    }
