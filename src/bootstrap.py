from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any


class _EnvironmentRecordFilter(logging.Filter):
    """Prevent ok-script from writing every environment variable to its log."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage().lstrip()
        return not (message.startswith("env ") or message.startswith("__init__:env "))


def create_ok_application(config: Mapping[str, Any]):
    # Import lazily so pure decision tests do not need GUI/OCR native libraries.
    import ok

    framework_logger = logging.getLogger("ok")
    environment_filter = _EnvironmentRecordFilter()
    framework_logger.addFilter(environment_filter)
    try:
        return ok.OK(dict(config))
    finally:
        framework_logger.removeFilter(environment_filter)
