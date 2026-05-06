from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from telegram import Bot

import database.db as db
from services.drive import download_url, download_telegram_file, upload_file, FileTooLargeError
from config import MAX_CONCURRENT_UPLOADS, MAX_QUEUE_SIZE, DAILY_UPLOAD_LIMIT

logger = logging.getLogger(__name__)


@dataclass
class UploadTask:
    user_id: int
    chat_id: int
    status_msg_id: int
    upload_type: str          # "link" | "file"
    source: str               # URL or Telegram file_path URL
    filename: str = ""
    mime_type: str = "application/octet-stream"
    file_size: int = 0
    tokens: dict = field(default_factory=dict)


class QueueFullError(Exception):
    pass


class UploadQueue:
    def __init__(self):
        self._q: asyncio.Queue[UploadTask] = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        self._workers: list[asyncio.Task] = []

    @property
    def pending(self) -> int:
        return self._q.qsize()

    async def start(self, bot: Bot):
        for _ in range(MAX_CONCURRENT_UPLOADS):
            t = asyncio.create_task(self._worker(bot))
            self._workers.append(t)
        logger.info("Upload queue started (%d workers)", MAX_CONCURRENT_UPLOADS)

    async def enqueue(self, task: UploadTask) -> int:
        """Returns queue position. Raises QueueFullError if full."""
        if self._q.full():
            raise QueueFullError()
        await self._q.put(task)
        return self._q.qsize()

    async def _worker(self, bot: Bot):
        while True:
            task = await self._q.get()
            try:
                await self._process(task, bot)
            except Exception as exc:
                logger.exception("Worker uncaught error for user %s", task.user_id)
                try:
                    await bot.edit_message_text(
                        f"❌ خطای غیرمنتظره:\n{exc}",
                        chat_id=task.chat_id,
                        message_id=task.status_msg_id,
                    )
                except Exception:
                    pass
            finally:
                self._q.task_done()

    async def _process(self, task: UploadTask, bot: Bot):
        async def status(text: str):
            try:
                await bot.edit_message_text(text, chat_id=task.chat_id, message_id=task.status_msg_id)
            except Exception:
                pass

        # Re-check daily limit (user may have uploaded while in queue)
        can, used = await db.check_daily_limit(task.user_id, DAILY_UPLOAD_LIMIT)
        if not can:
            await status(
                f"❌ محدودیت روزانه ({DAILY_UPLOAD_LIMIT} فایل) پر شده است.\n"
                "فردا دوباره امتحان کنید."
            )
            return

        # Re-fetch tokens (may have been refreshed by another task)
        tokens = await db.get_tokens(task.user_id)
        if not tokens:
            await status("❌ اتصال به گوگل درایو قطع شده. لطفاً دوباره /start بزنید و OAuth را انجام دهید.")
            return

        tmp_path: Path | None = None
        try:
            # ── Download ──────────────────────────────────────
            if task.upload_type == "link":
                await status("⏬ در حال دانلود از لینک...")
                tmp_path, filename, mime_type, size = await download_url(task.source)
            else:
                await status("⏬ در حال دریافت فایل از تلگرام...")
                tmp_path, filename, size = await download_telegram_file(
                    task.source, task.filename, task.file_size
                )
                mime_type = task.mime_type

            size_mb = size / (1024 * 1024)
            await status(f"⬆️ در حال آپلود به گوگل درایو...\n📁 {filename} ({size_mb:.1f} MB)")

            # ── Upload to Drive (blocking I/O in executor) ────
            loop = asyncio.get_event_loop()
            file_meta, updated_tokens = await loop.run_in_executor(
                None, upload_file, tokens, tmp_path, filename, mime_type
            )

            # Persist refreshed tokens
            if updated_tokens.get("token") != tokens.get("token"):
                await db.save_tokens(task.user_id, updated_tokens)

            # Record in DB
            await db.increment_daily(task.user_id)
            await db.record_upload(
                task.user_id, filename, size, task.upload_type,
                file_meta["id"], file_meta["webViewLink"], file_meta["webContentLink"],
            )

            uploaded_mb = int(file_meta.get("size", size)) / (1024 * 1024)
            remaining = DAILY_UPLOAD_LIMIT - used - 1

            await status(
                f"✅ آپلود موفق!\n\n"
                f"📁 نام: {filename}\n"
                f"📦 حجم: {uploaded_mb:.2f} MB\n\n"
                f"🔗 [مشاهده در گوگل درایو]({file_meta['webViewLink']})\n"
                f"⬇️ [دانلود مستقیم]({file_meta['webContentLink']})\n\n"
                f"📊 آپلودهای باقی‌مانده امروز: {remaining}"
            )

        except FileTooLargeError as e:
            await status(str(e))
        except Exception as e:
            logger.exception("Upload failed for user %s", task.user_id)
            await status(f"❌ خطا در آپلود:\n{e}")
        finally:
            if tmp_path and tmp_path.exists():
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
