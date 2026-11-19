import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

import config
from database import init_db, create_appeal, set_user_state, get_user_state

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
if config.BOT_TOKEN:
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
else:
    bot = None
dp = Dispatcher()


# ===================== КЛАВИАТУРЫ =====================

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура бота."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Подать жалобу")],
            [KeyboardButton(text="ℹ️ Как это работает")]
        ],
        resize_keyboard=True
    )


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены в режиме ввода жалобы."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )


# ===================== ОБРАБОТЧИКИ КОМАНД И КНОПОК =====================

@dp.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message):
    """Приветственное сообщение при старте бота."""
    user_id = message.from_user.id if message.from_user else 0
    await asyncio.to_thread(set_user_state, user_id, None)

    welcome_text = (
        "👋 <b>Привет! Это анонимный бот оперотряда общежития.</b>\n\n"
        "Здесь ты можешь сообщить о нарушении, проблеме или происшествии. "
        "Все обращения передаются строго анонимно: твоё имя, username и ID нигде не раскрываются.\n\n"
        "👇 <b>Чтобы отправить обращение, нажми кнопку «📝 Подать жалобу» ниже.</b>"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard())


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


@dp.message(F.text.in_({"ℹ️ Как это работает", "Помощь"}), F.chat.type == "private")
@dp.message(Command("help"), F.chat.type == "private")
async def cmd_help(message: Message):
    """Справка по использованию бота."""
    help_text = (
        "ℹ️ <b>Как пользоваться ботом:</b>\n\n"
        "1. Нажмите кнопку <b>«📝 Подать жалобу»</b> (или команду /complaint).\n"
        "2. Отправьте описание ситуации, фото, видео или документ.\n"
        "3. Бот зарегистрирует обращение под уникальным номером и анонимно передаст оперотряду.\n"
        "4. Ваши личные данные <b>100% скрыты</b> — никто не узнает автора жалобы."
    )
    await message.answer(help_text, reply_markup=get_main_keyboard())


@dp.message(F.text == "❌ Отмена", F.chat.type == "private")
@dp.message(Command("cancel"), F.chat.type == "private")
async def cmd_cancel(message: Message):
    """Отмена текущего ввода жалобы."""
    user_id = message.from_user.id if message.from_user else 0
    await asyncio.to_thread(set_user_state, user_id, None)

    await message.answer(
        "🚫 <b>Подача жалобы отменена.</b>\nЕсли захотите отправить обращение позже, просто нажмите кнопку ниже.",
        reply_markup=get_main_keyboard()
    )


@dp.message(F.text == "📝 Подать жалобу", F.chat.type == "private")
@dp.message(Command("complaint", "report", "appeal"), F.chat.type == "private")
async def cmd_make_complaint(message: Message):
    """Переход в режим ожидания жалобы от пользователя."""
    user_id = message.from_user.id if message.from_user else 0
    await asyncio.to_thread(set_user_state, user_id, "waiting_for_complaint")

    prompt_text = (
        "✍️ <b>Опишите суть вашей жалобы:</b>\n\n"
        "Укажите важные детали (номер комнаты, этаж, что произошло).\n"
        "Вы также можете отправить <b>фото, видео, голосовое сообщение или файл</b>.\n\n"
        "<i>Следующее ваше сообщение будет анонимно передано дежурным оперотряда.</i>\n"
        "<i>(Если передумали — нажмите кнопку «❌ Отмена» ниже)</i>"
    )
    await message.answer(prompt_text, reply_markup=get_cancel_keyboard())


# ================== ПРИЕМ И ОБРАБОТКА ОБРАЩЕНИЙ ==================

@dp.message(F.chat.type == "private")
async def handle_private_message(message: Message):
    """
    Обрабатывает входящие сообщения в личном чате.
    Если пользователь нажал «Подать жалобу» — принимает обращение.
    Иначе — предлагает воспользоваться кнопкой.
    """
    user_id = message.from_user.id if message.from_user else 0
    state = await asyncio.to_thread(get_user_state, user_id)

    # Если пользователь НЕ нажимал "Подать жалобу"
    if state != "waiting_for_complaint":
        await message.answer(
            "👋 Чтобы отправить анонимное обращение оперативному отряду, "
            "нажмите кнопку <b>«📝 Подать жалобу»</b> ниже 👇",
            reply_markup=get_main_keyboard()
        )
        return

    # Пользователь находится в режиме подачи жалобы:
    content_type = message.content_type
    preview_text = message.text or message.caption or f"[{content_type}]"

    # Регистрируем жалобу в базе
    appeal_id = await asyncio.to_thread(
        create_appeal,
        user_id,
        str(content_type),
        preview_text[:200]
    )

    # Сбрасываем состояние пользователя обратно
    await asyncio.to_thread(set_user_state, user_id, None)

    now_str = datetime.now().strftime("%d.%m.%Y в %H:%M")
    logger.info(f"Получено новое обращение #{appeal_id:04d} (тип: {content_type})")

    # Пересылаем в группу оперотряда
    if config.GROUP_CHAT_ID:
        try:
            header = (
                f"🚨 <b>Новое анонимное обращение #{appeal_id:04d}</b>\n"
                f"📅 <i>{now_str}</i>\n"
                f"🔒 <i>Статус: Анонимно</i>\n"
                f"────────────────────────"
            )
            await bot.send_message(
                chat_id=config.GROUP_CHAT_ID,
                text=header
            )
            await bot.copy_message(
                chat_id=config.GROUP_CHAT_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            logger.info(f"Обращение #{appeal_id:04d} переслано в группу {config.GROUP_CHAT_ID}")
        except Exception as e:
            logger.error(f"Ошибка при пересылке обращения в группу: {e}")
    else:
        logger.warning(f"GROUP_CHAT_ID не настроен! Обращение #{appeal_id:04d} сохранено в базу данных.")

    # Подтверждение пользователю
    confirmation_text = (
        "🛡️ <b>Обращение принято!</b>\n\n"
        f"Ваша жалоба зарегистрирована под номером <b>#{appeal_id:04d}</b> "
        "и передана оперативному отряду.\n\n"
        "🤝 <i>Спасибо за неравнодушие! Обращение передано строго анонимно. "
        "Ситуация будет проверена.</i>"
    )
    await message.answer(confirmation_text, reply_markup=get_main_keyboard())


# ===================== ТОЧКА ВХОДА (ЛОКАЛЬНЫЙ ЗАПУСК) =====================

async def main():
    await asyncio.to_thread(init_db)
    logger.info("База данных инициализирована.")
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот оперотряда запущен и ожидает обращений...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
