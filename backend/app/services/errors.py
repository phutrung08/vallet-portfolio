from typing import Literal

RuleCode = Literal[
    "trip_locked",
    "trip_closed",
    "name_taken",
    "trip_full",
    "trip_limit_reached",
    "device_trip_limit_reached",
    "member_is_fund_holder",
    "member_already_joined",
    "last_member",
    "member_not_active",
    "no_fund",
    "fund_in_use",
    "invalid_split",
    "currency_not_supported",
    "no_bank_account",
    "idempotency_conflict",
    "version_conflict",
]


class RuleViolation(Exception):
    """A request the trip's rules refuse; the API turns ``code`` into a status and error body.

    ``difference`` (total minus the stated amounts) is set only for an exact split that does not
    add up, so the UI can say how much is missing or in excess.
    """

    def __init__(self, code: RuleCode, *, difference: int | None = None) -> None:
        super().__init__(code)
        self.code: RuleCode = code
        self.difference = difference


class InconsistentTripData(Exception):
    """Stored data breaks an invariant the services keep; a bug, never the client's fault."""
