"""
Entry point: runs the Telegram bot (polling) and the OAuth callback web server side-by-side.
"""

import asyncio
import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram.ext import Application

from bot import build_app
from database import init_db, get_user_id_by_state, save_tokens, delete_oauth_state
from auth import exchange_code
from config import SERVER_HOST, SERVER_PORT

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

bot_app: Application | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_app
    await init_db()
    bot_app = build_app()
    await bot_app.initialize()
    await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling(drop_pending_updates=True))
    logger.info("Bot started (polling)")
    yield
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()
    logger.info("Bot stopped")


web = FastAPI(lifespan=lifespan)

_SUCCESS_HTML = """
<!doctype html>
<html dir="rtl" lang="fa">
<head><meta charset="utf-8"><title>اتصال موفق</title>
<style>
  body {{ font-family: Tahoma, Arial, sans-serif; display: flex; align-items: center;
         justify-content: center; height: 100vh; margin: 0; background: #f0f2f5; }}
  .card {{ background: white; border-radius: 12px; padding: 40px 60px; text-align: center;
           box-shadow: 0 4px 20px rgba(0,0,0,.1); }}
  h1 {{ color: #4CAF50; }} p {{ color: #555; }}
</style></head>
<body><div class="card">
  <h1>✅ اتصال موفق!</h1>
  <p>حساب گوگل شما با موفقیت متصل شد.</p>
  <p>به تلگرام برگردید و شروع کنید.</p>
</div></body></html>
"""

_ERROR_HTML = """
<!doctype html>
<html dir="rtl" lang="fa">
<head><meta charset="utf-8"><title>خطا</title></head>
<body dir="rtl" style="font-family:Tahoma;text-align:center;padding:50px">
  <h1>❌ خطا</h1><p>{msg}</p>
</body></html>
"""


@web.get("/oauth/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    if error:
        return HTMLResponse(_ERROR_HTML.format(msg=error), status_code=400)

    if not code or not state:
        return HTMLResponse(_ERROR_HTML.format(msg="پارامترهای نامعتبر."), status_code=400)

    user_id = await get_user_id_by_state(state)
    if not user_id:
        return HTMLResponse(
            _ERROR_HTML.format(msg="Session منقضی شده. لطفاً دوباره /auth را در تلگرام بزنید."),
            status_code=400,
        )

    try:
        tokens = exchange_code(code)
    except Exception as e:
        logger.exception("Token exchange failed")
        return HTMLResponse(_ERROR_HTML.format(msg=str(e)), status_code=500)

    await save_tokens(user_id, tokens)
    await delete_oauth_state(state)

    if bot_app:
        try:
            await bot_app.bot.send_message(
                chat_id=user_id,
                text="✅ اتصال به گوگل درایو با موفقیت انجام شد!\n\nحالا لینک هر فایلی رو بفرستید تا آپلود کنم.",
            )
        except Exception:
            logger.warning("Could not notify user %s via Telegram", user_id)

    return HTMLResponse(_SUCCESS_HTML)


@web.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(web, host=SERVER_HOST, port=SERVER_PORT)
