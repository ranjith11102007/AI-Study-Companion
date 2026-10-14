import logging
import sys

from app.core.config import get_settings

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging() -> None:
    settings = get_settings()
    settings.log_dir.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if settings.debug else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)

    if not root.handlers:
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(stream)

        file_handler = logging.FileHandler(
            settings.log_dir / "app.log", encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(file_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
