from __future__ import annotations

import os
import tempfile
import logging
from pathlib import Path
from typing import Callable, Awaitable, Optional

import aiohttp
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from services.auth import get_credentials, creds_to_dict
from config import MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)

_MAX_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
_CHUNK = 512 * 1024
_DRIVE_CHUNK = 5 * 1024 * 1024


class FileTooLargeError(Exception):
    pass


class UploadCancelled(Exception):
    pass


async def download_url(
    url: str,
    progress_cb: Optional[Callable[[int, int], Awaitable[None]]] = None,
    cancelled_check: Optional[Callable[[], bool]] = None,
) -> tuple[Path, str, str, int]:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, allow_redirects=True) as resp:
            resp.raise_for_status()

            cl = resp.headers.get("Content-Length")
            if cl and int(cl) > _MAX_BYTES:
                raise FileTooLargeError(f"حجم فایل بیشتر از {MAX_FILE_SIZE_MB} مگابایت است.")

            cd = resp.headers.get("Content-Disposition", "")
            filename = None
            if "filename=" in cd:
                filename = cd.split("filename=")[-1].strip("\"' ")
            if not filename:
                filename = str(resp.url).split("?")[0].rstrip("/").split("/")[-1] or "file"

            mime_type = resp.headers.get("Content-Type", "application/octet-stream").split(";")[0].strip()
            total_size = int(cl) if cl else 0

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix="_drivebot")
            total = 0
            try:
                async for chunk in resp.content.iter_chunked(_CHUNK):
                    if cancelled_check and cancelled_check():
                        raise UploadCancelled()
                    total += len(chunk)
                    if total > _MAX_BYTES:
                        raise FileTooLargeError(f"حجم فایل بیشتر از {MAX_FILE_SIZE_MB} مگابایت است.")
                    tmp.write(chunk)
                    if progress_cb and total_size > 0:
                        await progress_cb(total, total_size)
                tmp.flush()
            except Exception:
                tmp.close()
                os.unlink(tmp.name)
                raise
            finally:
                tmp.close()

            return Path(tmp.name), filename, mime_type, total


async def download_telegram_file(
    file_path_url: str,
    filename: str,
    file_size: int,
    progress_cb: Optional[Callable[[int, int], Awaitable[None]]] = None,
    cancelled_check: Optional[Callable[[], bool]] = None,
) -> tuple[Path, str, int]:
    if file_size and file_size > _MAX_BYTES:
        raise FileTooLargeError(f"حجم فایل بیشتر از {MAX_FILE_SIZE_MB} مگابایت است.")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix="_drivebot")
    total = 0
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(file_path_url) as resp:
                resp.raise_for_status()
                async for chunk in resp.content.iter_chunked(_CHUNK):
                    if cancelled_check and cancelled_check():
                        raise UploadCancelled()
                    total += len(chunk)
                    if total > _MAX_BYTES:
                        raise FileTooLargeError(f"حجم فایل بیشتر از {MAX_FILE_SIZE_MB} مگابایت است.")
                    tmp.write(chunk)
                    if progress_cb and file_size > 0:
                        await progress_cb(total, file_size)
        tmp.flush()
    except Exception:
        tmp.close()
        os.unlink(tmp.name)
        raise
    finally:
        tmp.close()

    return Path(tmp.name), filename, total


def upload_file(
    tokens: dict,
    file_path: Path,
    filename: str,
    mime_type: str,
    sync_progress_cb: Optional[Callable[[int, int], None]] = None,
    cancelled_check: Optional[Callable[[], bool]] = None,
) -> tuple[dict, dict]:
    creds = get_credentials(tokens)
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    file_size = file_path.stat().st_size

    with open(file_path, "rb") as fh:
        media = MediaIoBaseUpload(fh, mimetype=mime_type, resumable=True, chunksize=_DRIVE_CHUNK)
        request = svc.files().create(
            body={"name": filename},
            media_body=media,
            fields="id,name,webViewLink,webContentLink,size",
        )

        response = None
        while response is None:
            if cancelled_check and cancelled_check():
                raise UploadCancelled()
            status, response = request.next_chunk()
            if status and sync_progress_cb and file_size > 0:
                sync_progress_cb(status.resumable_progress, file_size)

        file_meta = response

    svc.permissions().create(
        fileId=file_meta["id"],
        body={"role": "reader", "type": "anyone"},
    ).execute()

    return file_meta, creds_to_dict(creds)


def delete_file(tokens: dict, drive_file_id: str):
    creds = get_credentials(tokens)
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    svc.files().delete(fileId=drive_file_id).execute()


def get_drive_quota(tokens: dict) -> dict:
    """Returns storageQuota dict: limit, usage, usageInDrive (bytes as strings)."""
    creds = get_credentials(tokens)
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    result = svc.about().get(fields="storageQuota").execute()
    return result.get("storageQuota", {})