import os
import sys
import logging
import traceback
from pathlib import Path

# Гарантируем, что корневая папка проекта находится в sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Complaints Bot Webhook")

init_error = None
bot = None
dp = None

try:
    import config
    from database import init_db
    init_db()

    if not config.BOT_TOKEN:
        raise ValueError("BOT_TOKEN не найден в переменных окружения Vercel! Укажите его в Settings -> Environment Variables.")

    from bot import bot as _bot, dp as _dp
    from aiogram.types import Update
    bot = _bot
    dp = _dp
except Exception as e:
    init_error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
    logger.error(f"Ошибка инициализации: {init_error}")


async def process_telegram_update(request: Request):
    """Обработка вебхука от Telegram."""
    if init_error or not bot or not dp:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": init_error or "Bot not initialized"}
        )

    try:
        from aiogram.types import Update
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


async def process_set_webhook(request: Request):
    """Установка вебхука в Telegram."""
    if init_error or not bot:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Бот не может установить вебхук из-за ошибки инициализации",
                "details": init_error
            }
        )

    host = request.headers.get("x-forwarded-host") or request.url.netloc
    proto = request.headers.get("x-forwarded-proto", "https")
    webhook_url = f"{proto}://{host}/api/webhook"

    try:
        await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True
        )
        info = await bot.get_webhook_info()
        return {
            "status": "success",
            "message": f"Вебхук успешно установлен на {webhook_url}",
            "webhook_info": {
                "url": info.url,
                "has_custom_certificate": info.has_custom_certificate,
                "pending_update_count": info.pending_update_count
            }
        }
    except Exception as e:
        logger.error(f"Не удалось установить вебхук: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


async def process_webhook_info():
    """Проверка статуса вебхука."""
    if not bot:
        return JSONResponse(status_code=500, content={"error": init_error or "Bot not initialized"})
    try:
        info = await bot.get_webhook_info()
        return {
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "last_error_date": info.last_error_date,
            "last_error_message": info.last_error_message
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.api_route("/{path:path}", methods=["GET", "POST"])
async def catch_all(request: Request, path: str = ""):
    """Универсальный роут для любых путей на Vercel."""
    if request.method == "POST":
        return await process_telegram_update(request)

    clean_path = path.lower()
    if "set_webhook" in clean_path:
        return await process_set_webhook(request)

    if "webhook_info" in clean_path:
        return await process_webhook_info()

    if init_error:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Ошибка инициализации бота на Vercel",
                "details": init_error,
                "hint": "Убедитесь, что в Vercel добавлены BOT_TOKEN и GROUP_CHAT_ID в Settings -> Environment Variables."
            }
        )

    return {
        "status": "online",
        "service": "Complaints Telegram Bot",
        "path_received": path,
        "instructions": "Бот запущен. Для настройки вебхука перейдите на /set_webhook."
    }
