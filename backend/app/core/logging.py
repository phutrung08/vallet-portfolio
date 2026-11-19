"""Log setup that keeps secrets out of the output.

Handlers and Uvicorn loggers get a filter that redacts credential headers and token-shaped values
from every record as a safety net: the code never logs request bodies, cookies, or query strings.
"""

import logging
import re

from app.core.security import TOKEN_PATTERN

LOG_FORMAT = "%(levelname)s %(name)s %(message)s"
REDACTED = "[redacted]"
UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")

# "Cookie: a=b", "authorization=Bearer x", "'set-cookie': 'a=b'" and (b'cookie', b'a=b') alike:
# the rest of the line, or of the quoted string, is the secret.
_CREDENTIAL_HEADER = re.compile(
    r"""(?P<name>\b(?:set-cookie|cookie|authorization))(?P<sep>['"]?\s*[:=,]\s*)b?(?P<quote>['"]?)"""
    r"""[^\r\n'"]*""",
    re.IGNORECASE,
)
# Device session tokens and share tokens are 43 URL-safe characters.
_TOKEN_SHAPED = re.compile(rf"(?<![A-Za-z0-9_-]){TOKEN_PATTERN}(?![A-Za-z0-9_-])")


def redact(text: str) -> str:
    """Mask credential headers and token-shaped strings in ``text``."""
    masked = _CREDENTIAL_HEADER.sub(rf"\g<name>\g<sep>\g<quote>{REDACTED}", text)
    return _TOKEN_SHAPED.sub(REDACTED, masked)


class RedactingFilter(logging.Filter):
    """Logging filter that strips credential values from formatted messages and tracebacks."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Merging the args first means a secret passed as an argument is redacted too.
        record.msg = redact(record.getMessage())
        record.args = None
        if record.exc_info and not record.exc_text:
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
        elif record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True


def _ensure_redacting_filter(target: logging.Filterer) -> None:
    if not any(isinstance(f, RedactingFilter) for f in target.filters):
        target.addFilter(RedactingFilter())


def configure_logging() -> None:
    """Attach ``RedactingFilter`` to root handlers and Uvicorn loggers idempotently."""
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    for attached in root.handlers:
        _ensure_redacting_filter(attached)
    for name in UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(name)
        _ensure_redacting_filter(uvicorn_logger)
        for attached in uvicorn_logger.handlers:
            _ensure_redacting_filter(attached)
