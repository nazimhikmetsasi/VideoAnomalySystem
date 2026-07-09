import os
import logging
from logging.handlers import RotatingFileHandler


def setup_logging(name: str = 'video_pipeline', log_filename: str = 'app.log') -> logging.Logger:
    """Merkezi log yapilandirmasi — dosya boyutu sinirli (max 10MB, 3 yedek)."""
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
    log_dir = os.path.join(root, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    max_bytes = int(os.getenv('LOG_MAX_BYTES', 10 * 1024 * 1024))
    backup_count = int(os.getenv('LOG_BACKUP_COUNT', 3))
    level_name = os.getenv('LOG_LEVEL', 'INFO').upper()
    level = getattr(logging, level_name, logging.INFO)

    log_format = '[%(levelname)s] %(asctime)s - %(name)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(log_format, datefmt=date_format)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    file_handler = RotatingFileHandler(
        os.path.join(log_dir, log_filename),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
