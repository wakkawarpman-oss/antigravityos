from __future__ import annotations

import logging
from typing import Any


_configured = False


def _configure_structlog() -> None:
    global _configured
    if _configured:
        return
    try:
        import structlog

        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    except Exception:
        pass
    _configured = True


def get_logger(name: str):
    _configure_structlog()
    try:
        import structlog

        return structlog.get_logger(name)
    except Exception:
        return logging.getLogger(name)
