from fastapi import APIRouter, Response, status

from app.api.deps import AppSettings, DbSession, Now, ReadonlyDeviceId, clear_device_cookie
from app.services import devices

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/me/sign-out", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(
    device_id: ReadonlyDeviceId,
    session: DbSession,
    settings: AppSettings,
    now: Now,
    response: Response,
) -> None:
    """Revoke this browser's session without sliding its cookie beforehand."""
    if device_id is not None:
        await devices.revoke_device(session, device_id, now)
    clear_device_cookie(response, settings)
