"""Background task: delete expired public drive uploads from Google Drive."""
from __future__ import annotations

import asyncio
import logging
from functools import partial

import database.db as db
from services.drive import delete_file

logger = logging.getLogger(__name__)

_INTERVAL_SECONDS = 30 * 60  # run every 30 minutes


async def cleanup_expired_public_uploads():
    """Periodically delete files uploaded to public drives that have expired (>6h)."""
    while True:
        await asyncio.sleep(_INTERVAL_SECONDS)
        await _run_cleanup()


async def _run_cleanup():
    try:
        expired = await db.get_expired_public_uploads()
        if not expired:
            return

        logger.info("Cleanup: found %d expired public drive uploads", len(expired))
        loop = asyncio.get_running_loop()

        for record in expired:
            drive_id = record.get("public_drive_id")
            file_id = record.get("drive_file_id")

            if drive_id and file_id:
                drive = await db.get_public_drive_by_id(drive_id)
                if drive and drive.get("tokens"):
                    try:
                        await loop.run_in_executor(
                            None,
                            partial(delete_file, drive["tokens"], file_id),
                        )
                        logger.info("Cleanup: deleted Drive file %s from drive %d", file_id, drive_id)
                    except Exception as e:
                        logger.warning(
                            "Cleanup: could not delete Drive file %s: %s", file_id, e
                        )

            # Clear links from DB regardless of whether Drive delete succeeded
            # (if file already gone, we still want to stop retrying)
            await db.expire_upload(record["id"])

    except Exception:
        logger.exception("Error in public drive cleanup task")
