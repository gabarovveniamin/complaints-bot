import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from aiogram.types import Update

from bot import bot, dp
from database import init_db
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализируем базу данных (в /tmp на Vercel)
init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # При старте приложения проверяем инициализацию базы
    init_db()
    yield


app = FastAPI(title="Complaints Bot Webhook", lifespan=lifespan)


@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "Complaints Telegram Bot",
        "instructions": "Перейдите на /set_webhook для автоматической привязки вебхука Telegram."
    }


@app.post("/")
@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    """Прием обновлений от серверов Telegram."""
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@app.get("/set_webhook")
@app.get("/api/set_webhook")
async def set_webhook(request: Request):
    """
    Автоматическая регистрация вебхука в Telegram.
    Достаточно открыть этот URL в браузере после деплоя.
    """
    # Определяем реальный домен на Vercel
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


@app.get("/webhook_info")
@app.get("/api/webhook_info")
async def get_webhook_info():
    """Проверка текущего статуса вебхука."""
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
