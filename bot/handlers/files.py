from telegram import Update
from telegram.ext import ContextTypes

import database.db as db
from bot.keyboards import files_nav, main_menu

_PAGE = 10


def _fmt_size(b: int) -> str:
    if b >= 1024 ** 3:
        return f"{b / 1024**3:.2f} GB"
    if b >= 1024 ** 2:
        return f"{b / 1024**2:.1f} MB"
    return f"{b / 1024:.0f} KB"


async def files_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    _, offset_str = query.data.split(":")
    offset = int(offset_str)

    total = await db.count_user_uploads(user_id)
    if total == 0:
        await query.edit_message_text(
            "📭 هنوز فایلی آپلود نکرده‌اید.",
            reply_markup=main_menu(),
        )
        return

    uploads = await db.get_user_uploads(user_id, limit=_PAGE, offset=offset)

    lines = [f"📁 **فایل‌های آپلود‌شده** (صفحه {offset // _PAGE + 1})\n"]
    for i, up in enumerate(uploads, start=offset + 1):
        icon = "🔗" if up["upload_type"] == "link" else "📤"
        size = _fmt_size(up["file_size"])
        date = str(up["uploaded_at"])[:10]
        lines.append(
            f"{i}. {icon} [{up['filename']}]({up['drive_view_link']}) — {size} — {date}"
        )

    text = "\n".join(lines)
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=files_nav(offset, total, _PAGE),
    )
