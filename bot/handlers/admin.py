"""Admin panel — only accessible to users listed in ADMIN_IDS."""
from __future__ import annotations

import logging
from telegram import Update
from telegram.ext import ContextTypes

import database.db as db
from bot.keyboards import admin_menu, admin_user_actions, main_menu, back_to_menu
from bot.states import IDLE, ADMIN_SEARCH
from config import ADMIN_IDS

logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _fmt_size(b: int) -> str:
    if b >= 1024 ** 3:
        return f"{b / 1024**3:.2f} GB"
    if b >= 1024 ** 2:
        return f"{b / 1024**2:.1f} MB"
    return f"{b / 1024:.0f} KB"


# ── Entry points ──────────────────────────────────────────────

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("❌ شما دسترسی ادمین ندارید.")
        return
    context.user_data["state"] = IDLE
    await update.message.reply_text("🛡 **پنل مدیریت**", parse_mode="Markdown", reply_markup=admin_menu())


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not _is_admin(update.effective_user.id):
        await query.edit_message_text("❌ دسترسی ندارید.")
        return

    action = query.data  # e.g. "admin:search", "admin:stats", "admin:block:123"

    if action == "admin:search":
        context.user_data["state"] = ADMIN_SEARCH
        await query.edit_message_text(
            "🔍 شناسه عددی یا نام کاربری کاربر را بفرستید:",
            reply_markup=back_to_menu(),
        )

    elif action == "admin:stats":
        total = await db.get_total_users()
        await query.edit_message_text(
            f"📊 **آمار کلی**\n\n👥 کل کاربران: {total}",
            parse_mode="Markdown",
            reply_markup=admin_menu(),
        )

    elif action.startswith("admin:block:"):
        target_id = int(action.split(":")[-1])
        await db.set_blocked(target_id, True)
        await query.edit_message_text(
            f"🚫 کاربر `{target_id}` مسدود شد.",
            parse_mode="Markdown",
            reply_markup=admin_menu(),
        )

    elif action.startswith("admin:unblock:"):
        target_id = int(action.split(":")[-1])
        await db.set_blocked(target_id, False)
        await query.edit_message_text(
            f"✅ کاربر `{target_id}` رفع مسدودیت شد.",
            parse_mode="Markdown",
            reply_markup=admin_menu(),
        )

    elif action == "admin:menu":
        context.user_data["state"] = IDLE
        await query.edit_message_text("🛡 **پنل مدیریت**", parse_mode="Markdown", reply_markup=admin_menu())


async def handle_admin_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") != ADMIN_SEARCH:
        return
    if not _is_admin(update.effective_user.id):
        return

    query_text = update.message.text.strip()
    results = await db.search_users(query_text)

    if not results:
        await update.message.reply_text(
            "❌ کاربری یافت نشد.",
            reply_markup=back_to_menu(),
        )
        return

    for user in results[:3]:  # show max 3 matches
        await _send_user_card(update, context, user)

    context.user_data["state"] = IDLE


async def _send_user_card(update: Update, context: ContextTypes.DEFAULT_TYPE, user: dict):
    uid = user["user_id"]
    uploads = await db.get_user_uploads(uid, limit=5)
    upload_count = await db.count_user_uploads(uid)

    joined = str(user["joined_at"])[:10]
    blocked_status = "🚫 مسدود" if user["is_blocked"] else "✅ فعال"

    recent_files = ""
    if uploads:
        recent_files = "\n\n📋 **آخرین فایل‌ها:**\n"
        for up in uploads:
            icon = "🔗" if up["upload_type"] == "link" else "📤"
            size = _fmt_size(up["file_size"])
            recent_files += f"  {icon} {up['filename']} — {size} — {str(up['uploaded_at'])[:10]}\n"

    text = (
        f"👤 **اطلاعات کاربر**\n\n"
        f"🆔 شناسه: `{uid}`\n"
        f"👤 نام: {user['first_name']} {user.get('last_name') or ''}\n"
        f"📱 نام کاربری: @{user['username'] or '—'}\n"
        f"📅 عضویت: {joined}\n"
        f"🔒 وضعیت: {blocked_status}\n\n"
        f"📊 **آمار آپلود**\n"
        f"▪️ کل: {user['total_uploads']} فایل\n"
        f"▪️ با لینک: {user['total_link_ups']}\n"
        f"▪️ فایل مستقیم: {user['total_file_ups']}\n"
        f"▪️ حجم کل: {_fmt_size(user['total_size_bytes'])}\n"
        f"▪️ تعداد ثبت‌شده: {upload_count}"
        f"{recent_files}"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=admin_user_actions(uid, bool(user["is_blocked"])),
    )
