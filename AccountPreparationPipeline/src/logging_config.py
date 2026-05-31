from __future__ import annotations

import logging

from pythonjsonlogger import jsonlogger


def configure_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("pipeline")
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter: logging.Formatter = jsonlogger.JsonFormatter(  # type: ignore[no-untyped-call]
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "module"},
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.propagate = False
    return logger
