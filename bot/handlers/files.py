from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

import database.db as db
from bot.keyboards import files_manage_kb, main_menu
from services.drive import delete_file, get_drive_quota

logger = logging.getLogger(__name__)

_PAGE = 5


def _fmt_size(b: int) -> str:
    if b >= 1024 ** 3:
        return f"{b / 1024**3:.2f} GB"
    if b >= 1024 ** 2:
        return f"{b / 1024**2:.1f} MB"
    return f"{b / 1024:.0f} KB"


def _quota_line(quota: dict) -> str:
    try:
        used = int(quota.get("usageInDrive", 0))
        limit = int(quota.get("limit", 0))
        if limit == 0:
            return ""
        pct = int(used / limit * 100)
        return f"\n☁️ فضای درایو: {_fmt_size(used)} / {_fmt_size(limit)} ({pct}%)\n"
    except Exception:
        return ""


async def files_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    _, offset_str = query.data.split(":")
    offset = int(offset_str)

    total = await db.count_user_uploads(user_id)
    if total == 0:
        await query.edit_message_text("📭 هنوز فایلی آپلود نکرده‌اید.", reply_markup=main_menu())
        return

    uploads = await db.get_user_uploads(user_id, limit=_PAGE, offset=offset)

    # Fetch Drive quota in background (non-blocking, best-effort)
    quota_line = ""
    tokens = await db.get_tokens(user_id)
    if tokens:
        try:
            loop = asyncio.get_event_loop()
            quota = await loop.run_in_executor(None, get_drive_quota, tokens)
            quota_line = _quota_line(quota)
        except Exception:
            pass

    page_num = offset // _PAGE + 1
    total_pages = (total + _PAGE - 1) // _PAGE
    lines = [f"📁 *فایل‌های آپلود‌شده* (صفحه {page_num}/{total_pages}){quota_line}\n"]

    for i, up in enumerate(uploads, start=offset + 1):
        icon = "🔗" if up["upload_type"] == "link" else "📤"
        size = _fmt_size(up["file_size"])
        date = str(up["uploaded_at"])[:10]
        name = up["filename"]
        link = up.get("drive_view_link", "")
        if link:
            lines.append(f"{i}\\. {icon} [{name}]({link}) — {size} — {date}")
        else:
            lines.append(f"{i}\\. {icon} {name} — {size} — {date}")

    lines.append("\n_روی نام فایل کلیک کنید تا در درایو باز شود._")
    lines.append("_برای حذف، دکمه‌های زیر را بزنید:_")

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
        reply_markup=files_manage_kb(uploads, offset, total, _PAGE),
    )


async def file_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    upload_id = int(query.data.split(":", 2)[2])

    record = await db.get_upload_by_id(upload_id)
    if not record or record["user_id"] != user_id:
        await query.answer("❌ فایل یافت نشد.", show_alert=True)
        return

    # Delete from Google Drive (best-effort)
    tokens = await db.get_tokens(user_id)
    if tokens and record.get("drive_file_id"):
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, delete_file, tokens, record["drive_file_id"])
        except Exception as e:
            logger.warning("Could not delete Drive file %s: %s", record["drive_file_id"], e)

    await db.delete_upload_record(upload_id)

    # Refresh the file list at same offset
    total = await db.count_user_uploads(user_id)
    offset = 0  # reset to first page after deletion

    if total == 0:
        await query.edit_message_text(
            "✅ فایل حذف شد.\n\n📭 دیگر فایلی وجود ندارد.",
            reply_markup=main_menu(),
        )
        return

    # Re-render the list
    uploads = await db.get_user_uploads(user_id, limit=_PAGE, offset=offset)
    page_num = 1
    total_pages = (total + _PAGE - 1) // _PAGE
    lines = [f"✅ فایل حذف شد\\.\n\n📁 *فایل‌های آپلود‌شده* (صفحه {page_num}/{total_pages})\n"]

    for i, up in enumerate(uploads, start=1):
        icon = "🔗" if up["upload_type"] == "link" else "📤"
        size = _fmt_size(up["file_size"])
        date = str(up["uploaded_at"])[:10]
        name = up["filename"]
        link = up.get("drive_view_link", "")
        if link:
            lines.append(f"{i}\\. {icon} [{name}]({link}) — {size} — {date}")
        else:
            lines.append(f"{i}\\. {icon} {name} — {size} — {date}")

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
        reply_markup=files_manage_kb(uploads, offset, total, _PAGE),
    )