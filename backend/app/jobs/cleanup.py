"""Delete expired data: ``python -m app.jobs.cleanup`` (run from cron; exits 1 on error)."""

import asyncio
import logging
import sys
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.config import get_settings
from app.core.db import create_engine
from app.core.logging import configure_logging
from app.services.cleanup import CleanupCounts, delete_expired_data

logger = logging.getLogger("app.jobs.cleanup")


async def run(engine: AsyncEngine, now: datetime) -> CleanupCounts:
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        return await delete_expired_data(session, now)


async def _main() -> None:
    engine = create_engine(get_settings().database_url)
    try:
        counts = await run(engine, datetime.now(UTC))
    finally:
        await engine.dispose()
    logger.info(
        "cleanup done: devices=%d idempotency_keys=%d", counts.devices, counts.idempotency_keys
    )


def main() -> int:
    configure_logging()
    try:
        asyncio.run(_main())
    except Exception:
        logger.exception("cleanup failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
