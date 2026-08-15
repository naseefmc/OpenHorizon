"""Application logging setup.

SDR §27.1: API credentials must never be written into logs. Any
attribute named `api_key`, `token`, or `password` on a log record is
redacted before formatting.
"""

import logging
import sys

_REDACT_KEYS = ("api_key", "apikey", "token", "password", "secret")


class RedactSensitiveFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for key in _REDACT_KEYS:
            if key in record.__dict__:
                record.__dict__[key] = "***REDACTED***"
        return True


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    )
    handler.addFilter(RedactSensitiveFilter())

    root.handlers.clear()
    root.addHandler(handler)
