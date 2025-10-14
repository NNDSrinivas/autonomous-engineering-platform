import sys

from loguru import logger

from .config import settings


def setup_logging():
    logger.remove()
    logger.add(sys.stdout, level=settings.log_level, backtrace=False, diagnose=False)
    return logger
