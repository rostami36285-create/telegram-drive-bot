from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from .start import start_command, check_join_callback
from .account import account_callback, disconnect_drive_callback
from .upload import (
    upload_link_callback, upload_file_callback,
    handle_url_message, handle_file_message,
)
from .files import files_callback
from .admin import admin_command, admin_callback, handle_admin_search, handle_admin_add_channel
from bot.keyboards import main_menu
from bot.states import IDLE


async def _main_menu_callback(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data["state"] = IDLE
    await query.edit_message_text("یک گزینه را انتخاب کنید:", reply_markup=main_menu())


def register(app: Application):
    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_command))

    # Callback queries — ordered by specificity
    app.add_handler(CallbackQueryHandler(check_join_callback,        pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(_main_menu_callback,        pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(account_callback,           pattern="^account$"))
    app.add_handler(CallbackQueryHandler(disconnect_drive_callback,  pattern="^disconnect_drive$"))
    app.add_handler(CallbackQueryHandler(upload_link_callback,       pattern="^upload_link$"))
    app.add_handler(CallbackQueryHandler(upload_file_callback,       pattern="^upload_file$"))
    app.add_handler(CallbackQueryHandler(files_callback,             pattern="^files:"))
    app.add_handler(CallbackQueryHandler(admin_callback,             pattern="^admin:"))

    # Text messages — route by state
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _route_text))

    # File messages
    app.add_handler(MessageHandler(
        (filters.Document.ALL | filters.VIDEO | filters.AUDIO) & ~filters.COMMAND,
        handle_file_message,
    ))


async def _route_text(update, context):
    state = context.user_data.get("state", IDLE)
    if state == "wait_url":
        await handle_url_message(update, context)
    elif state == "admin_search":
        await handle_admin_search(update, context)
    elif state == "admin_add_channel":
        await handle_admin_add_channel(update, context)
