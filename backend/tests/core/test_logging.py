import io
import logging
import sys

import pytest

from app.core.logging import (
    LOG_FORMAT,
    REDACTED,
    UVICORN_LOGGERS,
    RedactingFilter,
    configure_logging,
    redact,
)
from app.core.security import new_token

TOKEN = new_token()


@pytest.mark.parametrize(
    "line",
    [
        "Cookie: __Host-vl_device=abc123; other=1",
        "cookie=vl_device=abc123",
        "Set-Cookie: vl_device=abc123; HttpOnly; Secure",
        "Authorization: Bearer abc123",
        "authorization: abc123",
        "headers {'cookie': 'vl_device=abc123', 'host': 'x'}",
        "scope headers [(b'cookie', b'vl_device=abc123'), (b'host', b'x')]",
        'headers {"Authorization": "Bearer abc123"}',
    ],
)
def test_credential_headers_lose_their_values(line: str) -> None:
    redacted = redact(line)

    assert "abc123" not in redacted
    assert REDACTED in redacted


def test_the_rest_of_a_quoted_header_survives() -> None:
    assert redact("{'cookie': 'vl_device=abc123', 'host': 'x'}") == (
        f"{{'cookie': '{REDACTED}', 'host': 'x'}}"
    )


def test_token_shaped_values_are_redacted_wherever_they_appear() -> None:
    assert redact(f"join with {TOKEN} failed") == f"join with {REDACTED} failed"
    assert redact(f"vl_device={TOKEN}") == f"vl_device={REDACTED}"


@pytest.mark.parametrize(
    "line",
    [
        "Unhandled error on GET /trips/6f1c2c1e-9b1e-4f7a-8f0e-0123456789ab/expenses",
        "member_not_active for 00000000-0000-4000-8000-000000000001",
        "plain message, nothing to hide",
        "a" * 42,
        "a" * 44,
    ],
)
def test_ordinary_text_is_left_alone(line: str) -> None:
    assert redact(line) == line


def make_record(msg: str, *args: object) -> logging.LogRecord:
    return logging.LogRecord("t", logging.INFO, __file__, 1, msg, args or None, None)


def test_the_filter_redacts_the_message_and_its_arguments() -> None:
    record = make_record("token %s and cookie %s", TOKEN, "Cookie: vl_device=abc123")

    assert RedactingFilter().filter(record) is True

    assert record.getMessage() == f"token {REDACTED} and cookie Cookie: {REDACTED}"


def test_the_filter_redacts_mapping_arguments() -> None:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "%(t)s", ({"t": TOKEN},), None)

    RedactingFilter().filter(record)

    assert record.getMessage() == REDACTED


def test_the_filter_redacts_tracebacks() -> None:
    try:
        raise RuntimeError(f"Authorization: Bearer abc123 {TOKEN}")
    except RuntimeError:
        record = logging.LogRecord("t", logging.ERROR, __file__, 1, "boom", None, sys.exc_info())

    RedactingFilter().filter(record)

    assert record.exc_text is not None
    assert "abc123" not in record.exc_text
    assert TOKEN not in record.exc_text


def test_configure_logging_filters_every_root_handler_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = logging.getLogger()
    existing = logging.StreamHandler()
    monkeypatch.setattr(root, "handlers", [existing])

    configure_logging()
    configure_logging()

    assert [type(f) for f in existing.filters] == [RedactingFilter]


def test_configure_logging_adds_a_plain_handler_when_there_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", [])
    monkeypatch.setattr(root, "level", logging.WARNING)

    configure_logging()

    (handler,) = root.handlers
    assert handler.formatter is not None
    assert handler.formatter._fmt == LOG_FORMAT
    assert [type(f) for f in handler.filters] == [RedactingFilter]
    assert root.level == logging.INFO


@pytest.mark.parametrize("logger_name", UVICORN_LOGGERS)
def test_configure_logging_filters_non_propagating_uvicorn_loggers_once(
    monkeypatch: pytest.MonkeyPatch, logger_name: str
) -> None:
    logger = logging.getLogger(logger_name)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    monkeypatch.setattr(logger, "handlers", [handler])
    monkeypatch.setattr(logger, "filters", [])
    monkeypatch.setattr(logger, "propagate", False)
    monkeypatch.setattr(logger, "level", logging.INFO)

    configure_logging()
    configure_logging()

    assert [type(f) for f in logger.filters] == [RedactingFilter]
    assert [type(f) for f in handler.filters] == [RedactingFilter]

    logger.info("Cookie: __Host-vl_device=%s", TOKEN)
    output = stream.getvalue()
    assert TOKEN not in output
    assert REDACTED in output


def test_a_logged_secret_is_redacted_by_the_configured_handler(
    caplog: pytest.LogCaptureFixture,
) -> None:
    configure_logging()

    logging.getLogger("app.test").error("Cookie: vl_device=%s", TOKEN)

    assert TOKEN not in caplog.text
    assert REDACTED in caplog.text
