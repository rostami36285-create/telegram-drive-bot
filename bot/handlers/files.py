from __future__ import annotations

import asyncio
import html
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


def _file_lines(uploads: list[dict], offset: int) -> list[str]:
    lines = []
    for i, up in enumerate(uploads, start=offset + 1):
        icon = "🔗" if up["upload_type"] == "link" else "📤"
        size = _fmt_size(up["file_size"])
        date = str(up["uploaded_at"])[:10]
        name = html.escape(up["filename"])
        link = up.get("drive_view_link", "")
        expired = link == "[منقضی شده]" or up.get("drive_dl_link") == "[منقضی شده]"
        if expired:
            lines.append(f"{i}. {icon} {name} — {size} — {date} <i>(منقضی شده)</i>")
        elif link:
            lines.append(f'{i}. {icon} <a href="{link}">{name}</a> — {size} — {date}')
        else:
            lines.append(f"{i}. {icon} {name} — {size} — {date}")
    return lines


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

    quota_line = ""
    try:
        tokens = await db.get_tokens(user_id)
        if tokens:
            loop = asyncio.get_running_loop()
            quota = await loop.run_in_executor(None, get_drive_quota, tokens)
            quota_line = _quota_line(quota)
    except Exception:
        pass

    page_num = offset // _PAGE + 1
    total_pages = (total + _PAGE - 1) // _PAGE

    lines = [f"📁 <b>فایل‌های آپلود‌شده</b> (صفحه {page_num}/{total_pages}){quota_line}\n"]
    lines.extend(_file_lines(uploads, offset))
    lines.append("\n<i>روی نام فایل کلیک کنید تا در درایو باز شود.</i>")
    lines.append("<i>برای حذف، دکمه‌های زیر را بزنید:</i>")

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="HTML",
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

    tokens = await db.get_tokens(user_id)
    if tokens and record.get("drive_file_id"):
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, delete_file, tokens, record["drive_file_id"])
        except Exception as e:
            logger.warning("Could not delete Drive file %s: %s", record["drive_file_id"], e)

    await db.delete_upload_record(upload_id)

    total = await db.count_user_uploads(user_id)
    if total == 0:
        await query.edit_message_text(
            "✅ فایل حذف شد.\n\n📭 دیگر فایلی وجود ندارد.",
            reply_markup=main_menu(),
        )
        return

    uploads = await db.get_user_uploads(user_id, limit=_PAGE, offset=0)
    total_pages = (total + _PAGE - 1) // _PAGE

    lines = [f"✅ فایل حذف شد.\n\n📁 <b>فایل‌های آپلود‌شده</b> (صفحه 1/{total_pages})\n"]
    lines.extend(_file_lines(uploads, 0))
    lines.append("\n<i>برای حذف، دکمه‌های زیر را بزنید:</i>")

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=files_manage_kb(uploads, 0, total, _PAGE),
    )