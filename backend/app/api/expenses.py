from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession, Now, TripMember
from app.api.idempotency import IdempotentCreate
from app.api.schemas.expenses import (
    CreateExpenseRequest,
    DaysOut,
    DaySummaryOut,
    EditExpenseRequest,
    ExpenseListOut,
    ExpenseOut,
)
from app.services import expense_edits, expense_reads, expenses

router = APIRouter(prefix="/trips/{trip_id}", tags=["expenses"])


@router.post("/expenses", status_code=status.HTTP_201_CREATED)
async def create_expense(
    body: CreateExpenseRequest, caller: TripMember, session: DbSession, once: IdempotentCreate
) -> ExpenseOut:
    """Create a new trip expense and compute deterministic shares server-side."""

    async def write() -> ExpenseOut:
        created = await expenses.create_expense(
            session, caller.trip_id, caller.member_id, body.to_new_expense()
        )
        if created is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND)
        return ExpenseOut.model_validate(created)

    return await once.run(body, ExpenseOut, write)


@router.get("/expenses")
async def list_expenses_on_day(
    day: Annotated[date, Query()], caller: TripMember, session: DbSession
) -> ExpenseListOut:
    """List live expenses recorded for a specific trip day."""
    listed = await expense_reads.list_day(session, caller.trip_id, day)
    return ExpenseListOut(expenses=[ExpenseOut.model_validate(item) for item in listed])


# Registered before /expenses/{expense_id} so "days" is never parsed as an expense UUID.
@router.get("/expenses/days")
async def list_expense_days(caller: TripMember, session: DbSession) -> DaysOut:
    """List daily expense counts and totals for the trip."""
    days = await expense_reads.list_days(session, caller.trip_id)
    return DaysOut(days=[DaySummaryOut.model_validate(day) for day in days])


@router.get("/expenses/{expense_id}")
async def get_expense(expense_id: UUID, caller: TripMember, session: DbSession) -> ExpenseOut:
    """Fetch a single live expense and its shares."""
    found = await expense_reads.get_expense(session, caller.trip_id, expense_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return ExpenseOut.model_validate(found)


@router.put("/expenses/{expense_id}")
async def edit_expense(
    expense_id: UUID,
    body: EditExpenseRequest,
    caller: TripMember,
    session: DbSession,
    now: Now,
) -> ExpenseOut:
    """Edit an expense if its optimistic concurrency version matches the current row."""
    edited = await expense_edits.edit_expense(
        session,
        caller.trip_id,
        expense_id,
        caller.member_id,
        body.to_new_expense(),
        body.version,
        now,
    )
    if edited is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return ExpenseOut.model_validate(edited)


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: UUID, caller: TripMember, session: DbSession, now: Now
) -> None:
    """Soft-delete a live expense."""
    deleted = await expense_edits.delete_expense(
        session, caller.trip_id, expense_id, caller.member_id, now
    )
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
