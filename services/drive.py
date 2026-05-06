from __future__ import annotations

import os
import tempfile
import logging
from pathlib import Path

import aiohttp
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from services.auth import get_credentials, creds_to_dict
from config import MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)

_MAX_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
_CHUNK = 512 * 1024        # 512 KB download chunks
_DRIVE_CHUNK = 5 * 1024 * 1024  # 5 MB upload chunks


class FileTooLargeError(Exception):
    pass


# ── Download helpers ──────────────────────────────────────────

async def download_url(url: str) -> tuple[Path, str, str, int]:
    """Download URL to a temp file. Returns (path, filename, mime_type, size_bytes)."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, allow_redirects=True) as resp:
            resp.raise_for_status()

            cl = resp.headers.get("Content-Length")
            if cl and int(cl) > _MAX_BYTES:
                raise FileTooLargeError(f"حجم فایل بیشتر از {MAX_FILE_SIZE_MB} مگابایت است.")

            # Resolve filename
            cd = resp.headers.get("Content-Disposition", "")
            filename = None
            if "filename=" in cd:
                filename = cd.split("filename=")[-1].strip("\"' ")
            if not filename:
                filename = str(resp.url).split("?")[0].rstrip("/").split("/")[-1] or "file"

            mime_type = resp.headers.get("Content-Type", "application/octet-stream").split(";")[0].strip()

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix="_drivebot")
            total = 0
            try:
                async for chunk in resp.content.iter_chunked(_CHUNK):
                    total += len(chunk)
                    if total > _MAX_BYTES:
                        raise FileTooLargeError(f"حجم فایل بیشتر از {MAX_FILE_SIZE_MB} مگابایت است.")
                    tmp.write(chunk)
                tmp.flush()
            except Exception:
                tmp.close()
                os.unlink(tmp.name)
                raise
            finally:
                tmp.close()

            return Path(tmp.name), filename, mime_type, total


async def download_telegram_file(file_path_url: str, filename: str, file_size: int) -> tuple[Path, str, int]:
    """Download a file from Telegram's CDN to a temp file."""
    if file_size and file_size > _MAX_BYTES:
        raise FileTooLargeError(f"حجم فایل بیشتر از {MAX_FILE_SIZE_MB} مگابایت است.")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix="_drivebot")
    total = 0
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(file_path_url) as resp:
                resp.raise_for_status()
                async for chunk in resp.content.iter_chunked(_CHUNK):
                    total += len(chunk)
                    if total > _MAX_BYTES:
                        raise FileTooLargeError(f"حجم فایل بیشتر از {MAX_FILE_SIZE_MB} مگابایت است.")
                    tmp.write(chunk)
        tmp.flush()
    except Exception:
        tmp.close()
        os.unlink(tmp.name)
        raise
    finally:
        tmp.close()

    return Path(tmp.name), filename, total


# ── Upload to Drive ───────────────────────────────────────────

def upload_file(tokens: dict, file_path: Path, filename: str, mime_type: str) -> tuple[dict, dict]:
    """Upload file_path to Google Drive. Returns (file_metadata, updated_tokens)."""
    creds = get_credentials(tokens)
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)

    with open(file_path, "rb") as fh:
        media = MediaIoBaseUpload(fh, mimetype=mime_type, resumable=True, chunksize=_DRIVE_CHUNK)
        file_meta = (
            svc.files()
            .create(
                body={"name": filename},
                media_body=media,
                fields="id,name,webViewLink,webContentLink,size",
            )
            .execute()
        )

    # Share: anyone with link can read
    svc.permissions().create(
        fileId=file_meta["id"],
        body={"role": "reader", "type": "anyone"},
    ).execute()

    return file_meta, creds_to_dict(creds)


def delete_file(tokens: dict, drive_file_id: str):
    creds = get_credentials(tokens)
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    svc.files().delete(fileId=drive_file_id).execute()
