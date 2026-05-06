import io
import aiohttp
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from auth import get_credentials, credentials_to_dict
from config import MAX_FILE_SIZE_MB


class FileTooLargeError(Exception):
    pass


async def fetch_file(url: str) -> tuple[io.BytesIO, str, str]:
    """Download a file from URL. Returns (stream, filename, mime_type)."""
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024

    async with aiohttp.ClientSession() as session:
        async with session.get(url, allow_redirects=True) as resp:
            resp.raise_for_status()

            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise FileTooLargeError(
                    f"حجم فایل بیشتر از {MAX_FILE_SIZE_MB} مگابایت است."
                )

            # Stream download while checking size
            buf = io.BytesIO()
            downloaded = 0
            async for chunk in resp.content.iter_chunked(1024 * 256):
                downloaded += len(chunk)
                if downloaded > max_bytes:
                    raise FileTooLargeError(
                        f"حجم فایل بیشتر از {MAX_FILE_SIZE_MB} مگابایت است."
                    )
                buf.write(chunk)

            buf.seek(0)

            # Resolve filename
            cd = resp.headers.get("Content-Disposition", "")
            filename = None
            if "filename=" in cd:
                filename = cd.split("filename=")[-1].strip("\"' ")
            if not filename:
                path = str(resp.url).split("?")[0].rstrip("/")
                filename = path.split("/")[-1] or "file"

            mime_type = resp.headers.get("Content-Type", "application/octet-stream")
            mime_type = mime_type.split(";")[0].strip()

            return buf, filename, mime_type


def upload_to_drive(tokens: dict, stream: io.BytesIO, filename: str, mime_type: str) -> tuple[dict, dict]:
    """Upload stream to Google Drive. Returns (file_metadata, updated_tokens)."""
    creds = get_credentials(tokens)
    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    media = MediaIoBaseUpload(stream, mimetype=mime_type, resumable=True, chunksize=1024 * 1024 * 5)

    file = (
        service.files()
        .create(
            body={"name": filename},
            media_body=media,
            fields="id,name,webViewLink,webContentLink,size",
        )
        .execute()
    )

    # Share with anyone who has the link (read-only)
    service.permissions().create(
        fileId=file["id"],
        body={"role": "reader", "type": "anyone"},
    ).execute()

    updated_tokens = credentials_to_dict(creds)
    return file, updated_tokens
