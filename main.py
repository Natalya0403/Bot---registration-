import os
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, Update
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# Ваши импорты из первого файла (FastAPI и БД)
from db.connect import init_db
from routes import router

# Ваши импорты из второго файла (Бот)
from handlers import routes as handlers_router
from middleware.rate_limit import RateLimitMiddleware
from notify import send_reminder

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
# Сюда подставится ваша публичная ссылка от ngrok (или домен)
WEBHOOK_HOST = os.getenv("API_URL", "https://bot-registration-n715.onrender.com").strip()
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO)

# Инициализируем бота и диспетчер (из вашего второго файла)
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

# Подключаем middleware и роутеры бота
dp.message.middleware(RateLimitMiddleware(limit_seconds=1.0))
dp.include_router(handlers_router.router)


# --- Жизненный цикл приложения (объединяет FastAPI, БД и бота) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Инициализируем базу данных (из вашего первого файла)
    await init_db()

    # (Закомментированный код для тестов уроков, если нужен)
    # today = date.today()
    # tomorrow = today + timedelta(days=1)
    # await create_lesson("Python - старт", today, 5,'https://itproger.com/')
    # await create_lesson("Создание Telegram бота", tomorrow, 3, 'https://www.bing.com/')

    # 2. Устанавливаем команды бота (из второго файла)
    await bot.set_my_commands([
        BotCommand(command="start", description="Перезапустить бота"),
        BotCommand(command="calendar", description="Запись на уроки"),
        BotCommand(command="profile", description="Личный кабинет"),
        BotCommand(command="admin", description="Панель администратора")
    ])

    # 3. Запускаем фоновые напоминания
    reminder_task = asyncio.create_task(send_reminder(bot))

    # 4. Регистрируем вебхук в Telegram
    await bot.set_webhook(url=WEBHOOK_URL)
    logging.info(f"Вебхук успешно установлен на адрес: {WEBHOOK_URL}")

    yield

    # --- Действия при выключении сервера ---
    reminder_task.cancel()
    await bot.delete_webhook()
    await bot.session.close()
    logging.info("Сервер остановлен, вебхук удален.")


# Создаем единое FastAPI-приложение
app = FastAPI(lifespan=lifespan)

# Подключаем ваши эндпоинты для сайта/админки (из первого файла)
app.include_router(router)


# --- Эндпоинт, куда Telegram шлет сообщения (Вебхуки) ---
@app.post(WEBHOOK_PATH)
async def bot_webhook(request: Request):
    update_data = await request.json()
    update = Update(**update_data)

    # Передаем обновление диспетчеру aiogram
    await dp.feed_update(bot=bot, update=update)

    return {"status": "ok"}