"""Handles both link-upload and file-upload flows."""
from __future__ import annotations

import secrets
import logging
import re

from telegram import Update, Document, Video, Audio
from telegram.ext import ContextTypes

import database.db as db
from bot.keyboards import main_menu, cancel_and_menu, connect_drive
from bot.states import IDLE, WAIT_URL, WAIT_FILE
from bot.rate_limiter import limiter
from services.auth import get_auth_url
from services.queue import UploadTask, QueueFullError
from config import DAILY_UPLOAD_LIMIT, MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)
_URL_RE = re.compile(r"https?://[^\s<>\"{}|\\^`\[\]]+")


# ── Shared pre-upload checks ──────────────────────────────────

async def _guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Returns True if user can proceed. Handles blocks, rate-limit, daily-limit, OAuth."""
    query = update.callback_query
    user_id = update.effective_user.id

    if await db.is_blocked(user_id):
        txt = "⛔ حساب شما مسدود است."
        if query:
            await query.edit_message_text(txt)
        else:
            await update.message.reply_text(txt)
        return False

    if not limiter.is_allowed(user_id):
        txt = (
            "⚠️ لطفاً اسپم نکنید!\n"
            "عملیات قبلی هنوز در حال انجام است یا درخواست‌های زیادی فرستادید.\n"
            "چند ثانیه صبر کنید."
        )
        if query:
            await query.answer(txt, show_alert=True)
        else:
            await update.message.reply_text(txt)
        return False

    can, used = await db.check_daily_limit(user_id, DAILY_UPLOAD_LIMIT)
    if not can:
        txt = f"❌ محدودیت روزانه ({DAILY_UPLOAD_LIMIT} فایل) پر شده است. فردا دوباره امتحان کنید."
        if query:
            await query.edit_message_text(txt, reply_markup=main_menu())
        else:
            await update.message.reply_text(txt, reply_markup=main_menu())
        return False

    return True


async def _ensure_oauth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """If user has no Drive token, send auth link and return False."""
    user_id = update.effective_user.id
    if await db.has_tokens(user_id):
        return True

    state = secrets.token_urlsafe(32)
    await db.save_oauth_state(state, user_id)
    auth_url = get_auth_url(state)

    query = update.callback_query
    text = (
        "☁️ **اتصال به گوگل درایو**\n\n"
        "برای آپلود، ابتدا حساب گوگل خود را متصل کنید.\n"
        "روی دکمه زیر کلیک کنید و پس از تأیید به ربات برگردید:"
    )
    if query:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=connect_drive(auth_url))
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=connect_drive(auth_url))
    return False


# ── Upload via link ───────────────────────────────────────────

async def upload_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not await _guard(update, context):
        return
    if not await _ensure_oauth(update, context):
        return

    context.user_data["state"] = WAIT_URL
    await query.edit_message_text(
        "🔗 **آپلود با لینک**\n\n"
        "لینک مستقیم فایل را ارسال کنید:\n"
        f"_(حداکثر حجم: {MAX_FILE_SIZE_MB // 1024} گیگابایت)_",
        parse_mode="Markdown",
        reply_markup=cancel_and_menu(),
    )


async def handle_url_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") != WAIT_URL:
        return

    urls = _URL_RE.findall(update.message.text or "")
    if not urls:
        await update.message.reply_text(
            "❌ لینک معتبری یافت نشد. لطفاً یک URL کامل ارسال کنید.",
            reply_markup=cancel_and_menu(),
        )
        return

    if not await _guard(update, context):
        context.user_data["state"] = IDLE
        return

    user_id = update.effective_user.id
    tokens = await db.get_tokens(user_id)
    if not tokens:
        await _ensure_oauth(update, context)
        context.user_data["state"] = IDLE
        return

    context.user_data["state"] = IDLE
    queue = context.application.bot_data["upload_queue"]
    status_msg = await update.message.reply_text("⏳ در حال افزودن به صف آپلود...")

    task = UploadTask(
        user_id=user_id,
        chat_id=update.effective_chat.id,
        status_msg_id=status_msg.message_id,
        upload_type="link",
        source=urls[0],
        tokens=tokens,
    )

    try:
        pos = await queue.enqueue(task)
        if pos > 1:
            await status_msg.edit_text(
                f"📋 در صف آپلود هستید.\n"
                f"موقعیت شما: **{pos}**\n"
                "به محض رسیدن نوبت شروع می‌شود.",
                parse_mode="Markdown",
            )
    except QueueFullError:
        await status_msg.edit_text(
            "⚠️ سرور در حال حاضر پر است.\n"
            "لطفاً چند دقیقه دیگر امتحان کنید.",
        )


# ── Upload via Telegram file ──────────────────────────────────

async def upload_file_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not await _guard(update, context):
        return
    if not await _ensure_oauth(update, context):
        return

    context.user_data["state"] = WAIT_FILE
    await query.edit_message_text(
        "📤 **آپلود فایل**\n\n"
        "فایل خود را ارسال کنید.\n"
        f"_(حداکثر حجم: {MAX_FILE_SIZE_MB // 1024} گیگابایت — فایل‌های بزرگ‌تر از 2 گیگ را از طریق لینک آپلود کنید)_",
        parse_mode="Markdown",
        reply_markup=cancel_and_menu(),
    )


async def handle_file_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") != WAIT_FILE:
        return

    msg = update.message
    file_obj = msg.document or msg.video or msg.audio

    if not file_obj:
        await msg.reply_text(
            "❌ فایل معتبری دریافت نشد. لطفاً یک فایل ارسال کنید.",
            reply_markup=cancel_and_menu(),
        )
        return

    if not await _guard(update, context):
        context.user_data["state"] = IDLE
        return

    user_id = update.effective_user.id
    tokens = await db.get_tokens(user_id)
    if not tokens:
        await _ensure_oauth(update, context)
        context.user_data["state"] = IDLE
        return

    # Get file info
    filename = getattr(file_obj, "file_name", None) or "file"
    file_size = getattr(file_obj, "file_size", 0) or 0
    mime_type = getattr(file_obj, "mime_type", "application/octet-stream") or "application/octet-stream"

    # Check size early (Telegram gives us file_size)
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size and file_size > max_bytes:
        await msg.reply_text(
            f"❌ حجم فایل ({file_size / 1024**3:.2f} GB) بیشتر از حداکثر مجاز است.\n"
            "برای فایل‌های بزرگ از گزینه «آپلود با لینک» استفاده کنید.",
            reply_markup=main_menu(),
        )
        context.user_data["state"] = IDLE
        return

    # Get Telegram download URL
    tg_file = await context.bot.get_file(file_obj.file_id)
    file_path_url = tg_file.file_path  # direct HTTPS URL

    context.user_data["state"] = IDLE
    queue = context.application.bot_data["upload_queue"]
    status_msg = await msg.reply_text("⏳ در حال افزودن به صف آپلود...")

    task = UploadTask(
        user_id=user_id,
        chat_id=update.effective_chat.id,
        status_msg_id=status_msg.message_id,
        upload_type="file",
        source=file_path_url,
        filename=filename,
        mime_type=mime_type,
        file_size=file_size,
        tokens=tokens,
    )

    try:
        pos = await queue.enqueue(task)
        if pos > 1:
            await status_msg.edit_text(
                f"📋 در صف آپلود هستید.\nموقعیت: **{pos}**",
                parse_mode="Markdown",
            )
    except QueueFullError:
        await status_msg.edit_text(
            "⚠️ سرور در حال حاضر پر است. چند دقیقه دیگر امتحان کنید."
        )
