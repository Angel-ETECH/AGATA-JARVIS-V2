import logging
import sys
from pathlib import Path

LOG_FORMAT = "[%(levelname)s] %(asctime)s | %(name)s | %(message)s"
DATE_FORMAT = "%H:%M:%S"

_log_initialized = False


def setup_logging(level: int = logging.INFO, log_file: Path | None = None) -> logging.Logger:
    global _log_initialized

    logger = logging.getLogger("jarvis")
    logger.setLevel(level)

    if _log_initialized:
        return logger

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        logger.addHandler(handler)

        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
            file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
            logger.addHandler(file_handler)

    _log_initialized = True
    return logger


def get_logger(name: str = "jarvis") -> logging.Logger:
    return logging.getLogger(name)
