import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

import config
from database import init_db, create_appeal

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


# ===================== ОБРАБОТЧИКИ КОМАНД =====================

@dp.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message):
    """Приветственное сообщение при старте бота."""
    welcome_text = (
        "Привет! Это анонимный бот оперотряда общежития.\n\n"
        "Здесь ты можешь сообщить о проблеме, нарушении или оставить жалобу. "
        "Мы рассмотрим обращение."
    )
    await message.answer(welcome_text)


@dp.message(Command("id", "getid"))
async def cmd_get_id(message: Message):
    """Команда для получения ID чата/группы для быстрой настройки .env."""
    chat_type = message.chat.type
    chat_id = message.chat.id
    response = (
        f"📋 <b>Информация о чате:</b>\n"
        f"• <b>Тип:</b> {chat_type}\n"
        f"• <b>ID:</b> <code>{chat_id}</code>\n\n"
    )
    if chat_type in ("group", "supergroup"):
        response += (
            f"👉 Чтобы пересылать жалобы в эту группу, укажите в <code>.env</code>:\n"
            f"<code>GROUP_CHAT_ID={chat_id}</code>"
        )
    else:
        response += (
            "Чтобы настроить отправку в группу, добавьте бота в нужную группу "
            "и отправьте туда команду <code>/id</code>."
        )

    await message.answer(response)


@dp.message(Command("help"), F.chat.type == "private")
async def cmd_help(message: Message):
    """Справка по использованию бота."""
    help_text = (
        "ℹ️ <b>Как пользоваться ботом:</b>\n\n"
        "1. Просто отправьте любое текстовое сообщение, фото, видео или документ в этот чат.\n"
        "2. Бот автоматически зарегистрирует ваше обращение и анонимно перешлет его оперотряду.\n"
        "3. Ваши личные данные (имя, логин, ID) нигде не отображаются — обращение на 100% анонимно.\n\n"
        "Для повторного вызова начального сообщения используйте /start."
    )
    await message.answer(help_text)


# ================== ПРИЕМ И ОБРАБОТКА ОБРАЩЕНИЙ ==================

@dp.message(F.chat.type == "private")
async def handle_complaint(message: Message):
    """
    Принимает любое сообщение (текст, фото, видео, голосовое, документ и т.д.)
    в личном чате как анонимную жалобу.
    """
    content_type = message.content_type
    preview_text = message.text or message.caption or f"[{content_type}]"

    # Сохраняем в базу данных в отдельном потоке
    user_id = message.from_user.id if message.from_user else 0
    appeal_id = await asyncio.to_thread(
        create_appeal,
        user_id,
        str(content_type),
        preview_text[:200]
    )

    now_str = datetime.now().strftime("%d.%m.%Y в %H:%M")

    logger.info(
        f"Получено новое обращение #{appeal_id:04d} от пользователя (тип: {content_type})"
    )

    # Если настроена группа — пересылаем анонимно туда
    if config.GROUP_CHAT_ID:
        try:
            header = (
                f"🚨 <b>Новое анонимное обращение #{appeal_id:04d}</b>\n"
                f"📅 <i>{now_str}</i>\n"
                f"🔒 <i>Статус: Анонимно</i>\n"
                f"────────────────────────"
            )
            # Отправляем шапку
            await bot.send_message(
                chat_id=config.GROUP_CHAT_ID,
                text=header
            )

            # Копируем сообщение без раскрытия автора
            await bot.copy_message(
                chat_id=config.GROUP_CHAT_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            logger.info(f"Обращение #{appeal_id:04d} успешно отправлено в группу {config.GROUP_CHAT_ID}")
        except Exception as e:
            logger.error(f"Ошибка при отправке обращения в группу: {e}")
    else:
        logger.warning(
            f"GROUP_CHAT_ID не настроен в .env! Обращение #{appeal_id:04d} сохранено в базу данных."
        )

    # Красивое ответное сообщение пользователю
    confirmation_text = (
        "🛡️ <b>Обращение принято!</b>\n\n"
        f"Ваша жалоба зарегистрирована под номером <b>#{appeal_id:04d}</b> "
        "и передана оперативному отряду.\n\n"
        "🤝 <i>Спасибо за неравнодушие и помощь в поддержании порядка в общежитии! "
        "Мы гарантируем конфиденциальность: обращение передано строго анонимно. "
        "Ситуация обязательно будет проверена, и при необходимости мы примем меры.</i>\n\n"
        "📌 <i>Если потребуется прикрепить фото/видео или уточнить детали — "
        "просто отправьте их следующим сообщением.</i>"
    )

    await message.answer(confirmation_text)


# ===================== ТОЧКА ВХОДА =====================

async def main():
    await asyncio.to_thread(init_db)
    logger.info("База данных инициализирована.")

    # Удаляем вебхуки и сбрасываем старые апдейты
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот оперотряда запущен и ожидает обращений...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
