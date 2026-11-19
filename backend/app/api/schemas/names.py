"""Request field types for human-entered names and text; every request model uses these."""

from typing import Annotated

from pydantic import AfterValidator

from app.services.names import normalise_name, normalise_text


def _normalised(max_length: int) -> AfterValidator:
    def validate(value: str) -> str:
        return normalise_name(value, max_length)

    return AfterValidator(validate)


def _optional_text(max_length: int, *, multiline: bool = False) -> AfterValidator:
    def validate(value: str | None) -> str | None:
        return None if value is None else normalise_text(value, max_length, multiline=multiline)

    return AfterValidator(validate)


TripName = Annotated[str, _normalised(80)]
MemberName = Annotated[str, _normalised(40)]
ExpenseTitle = Annotated[str, _normalised(120)]
ExpenseNote = Annotated[str | None, _optional_text(500, multiline=True)]
ExpensePlace = Annotated[str | None, _optional_text(200)]
PaymentNote = Annotated[str | None, _optional_text(200)]
