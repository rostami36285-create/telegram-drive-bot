import re
import secrets
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from database import init_db, save_tokens, get_tokens, delete_tokens, save_oauth_state
from auth import get_auth_url
from drive import fetch_file, upload_to_drive, FileTooLargeError
from config import TELEGRAM_BOT_TOKEN, MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://[^\s<>\"{}|\\^`\[\]]+")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! 👋 به ربات آپلودر گوگل درایو خوش آمدید.\n\n"
        "با این ربات می‌توانید لینک هر فایلی را بفرستید تا در گوگل درایو شما آپلود شود.\n\n"
        "دستورات:\n"
        "/auth — اتصال به گوگل درایو\n"
        "/status — وضعیت اتصال\n"
        "/disconnect — قطع اتصال از گوگل درایو\n\n"
        "ابتدا با /auth حساب گوگل خود را متصل کنید."
    )


async def cmd_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tokens = await get_tokens(user_id)
    if tokens:
        await update.message.reply_text(
            "✅ شما قبلاً به گوگل درایو متصل هستید.\n"
            "برای قطع اتصال از /disconnect استفاده کنید."
        )
        return

    state = secrets.token_urlsafe(32)
    await save_oauth_state(state, user_id)
    auth_url = get_auth_url(state)

    keyboard = [[InlineKeyboardButton("🔗 اتصال به گوگل درایو", url=auth_url)]]
    await update.message.reply_text(
        "برای اتصال حساب گوگل، روی دکمه زیر کلیک کنید:\n\n"
        "⚠️ پس از تأیید، صفحه مرورگر را ببندید و به تلگرام برگردید.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tokens = await get_tokens(user_id)
    if tokens:
        await update.message.reply_text("✅ متصل به گوگل درایو هستید.")
    else:
        await update.message.reply_text("❌ به گوگل درایو متصل نیستید. از /auth استفاده کنید.")


async def cmd_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await delete_tokens(user_id)
    await update.message.reply_text("✅ اتصال به گوگل درایو قطع شد.")


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text or ""

    urls = URL_RE.findall(text)
    if not urls:
        return

    tokens = await get_tokens(user_id)
    if not tokens:
        await update.message.reply_text(
            "❌ ابتدا باید با /auth به گوگل درایو متصل شوید."
        )
        return

    url = urls[0]
    status = await update.message.reply_text("⏳ در حال دانلود فایل...")

    try:
        stream, filename, mime_type = await fetch_file(url)
        size_mb = stream.getbuffer().nbytes / (1024 * 1024)

        await status.edit_text(
            f"⬆️ در حال آپلود به گوگل درایو...\n"
            f"📁 {filename} ({size_mb:.1f} MB)"
        )

        loop = asyncio.get_event_loop()
        file_info, updated_tokens = await loop.run_in_executor(
            None, upload_to_drive, tokens, stream, filename, mime_type
        )

        # Save refreshed tokens if changed
        if updated_tokens.get("token") != tokens.get("token"):
            await save_tokens(user_id, updated_tokens)

        uploaded_mb = int(file_info.get("size", 0)) / (1024 * 1024)
        await status.edit_text(
            f"✅ فایل با موفقیت آپلود شد!\n\n"
            f"📁 نام: `{file_info['name']}`\n"
            f"📦 حجم: {uploaded_mb:.2f} MB\n\n"
            f"🔗 [مشاهده در گوگل درایو]({file_info['webViewLink']})\n"
            f"⬇️ [لینک دانلود مستقیم]({file_info['webContentLink']})",
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )

    except FileTooLargeError as e:
        await status.edit_text(f"❌ {e}\nحداکثر حجم مجاز: {MAX_FILE_SIZE_MB} MB")
    except Exception as e:
        logger.exception("Upload failed for user %s", user_id)
        await status.edit_text(f"❌ خطا در پردازش فایل:\n{e}")


def build_app() -> Application:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("auth", cmd_auth))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("disconnect", cmd_disconnect))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    return app
