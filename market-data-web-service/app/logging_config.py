import logging
import logging.handlers
import sys
from pathlib import Path

import structlog


def setup_logging() -> None:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "market-data-api.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
    )
    file_handler.setFormatter(logging.Formatter("%(message)s"))

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
