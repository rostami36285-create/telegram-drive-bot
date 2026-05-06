from __future__ import annotations

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError

import database.db as db
from bot.keyboards import main_menu, check_membership
from bot.states import IDLE

logger = logging.getLogger(__name__)


async def _check_channels(bot, user_id: int) -> list[str]:
    """Returns list of channel IDs (from DB) the user has NOT joined."""
    channels = await db.get_required_channels()
    not_joined = []
    for ch in channels:
        cid = ch["channel_id"]
        try:
            member = await bot.get_chat_member(chat_id=cid, user_id=user_id)
            if member.status in ("left", "kicked", "banned"):
                not_joined.append(cid)
        except TelegramError:
            not_joined.append(cid)
    return not_joined


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.get_or_create_user(
        user.id,
        user.username or "",
        user.first_name or "",
        user.last_name or "",
    )

    if await db.is_blocked(user.id):
        await update.message.reply_text(
            "⛔ حساب شما در این ربات مسدود شده است.\n"
            "برای اعتراض با پشتیبانی تماس بگیرید."
        )
        return

    await _show_start(update, context)


async def _show_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["state"] = IDLE

    not_joined = await _check_channels(context.bot, user.id)

    if not_joined:
        channels_info = []
        for ch in not_joined:
            try:
                chat = await context.bot.get_chat(ch)
                title = chat.title or ch
                link = chat.invite_link or f"https://t.me/{ch.lstrip('@')}"
                channels_info.append({"title": title, "url": link})
            except TelegramError:
                channels_info.append({"title": ch, "url": f"https://t.me/{ch.lstrip('@')}"})

        await update.message.reply_text(
            "👋 خوش آمدید!\n\n"
            "⚠️ برای استفاده از ربات، ابتدا در کانال‌های زیر عضو شوید:",
            reply_markup=check_membership(channels_info),
        )
        return

    await update.message.reply_text(
        f"👋 سلام {user.first_name}!\n\n"
        "به ربات آپلودر گوگل درایو خوش آمدید.\n"
        "یک گزینه را انتخاب کنید:",
        reply_markup=main_menu(),
    )


async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    if await db.is_blocked(user.id):
        await query.edit_message_text("⛔ حساب شما مسدود است.")
        return

    not_joined = await _check_channels(context.bot, user.id)

    if not_joined:
        channels_info = []
        for ch in not_joined:
            try:
                chat = await context.bot.get_chat(ch)
                title = chat.title or ch
                link = chat.invite_link or f"https://t.me/{ch.lstrip('@')}"
                channels_info.append({"title": title, "url": link})
            except TelegramError:
                channels_info.append({"title": ch, "url": f"https://t.me/{ch.lstrip('@')}"})

        await query.edit_message_text(
            "❌ هنوز در همه کانال‌ها عضو نشدید.\n\nلطفاً ابتدا عضو شوید:",
            reply_markup=check_membership(channels_info),
        )
        return

    context.user_data["state"] = IDLE
    await query.edit_message_text(
        "✅ عضویت تأیید شد!\n\nیک گزینه را انتخاب کنید:",
        reply_markup=main_menu(),
    )
