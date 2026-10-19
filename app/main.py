from fastapi import FastAPI
from db.connect import init_db
from contextlib import asynccontextmanager
from routes import router
from db.crud import create_lesson
from datetime import date, timedelta


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # today = date.today()
    # tomorrow = today + timedelta(days=1)
    # await create_lesson("Python - старт", today, 5,'https://itproger.com/')
    # await create_lesson("Создание Telegram бота", tomorrow, 3, 'https://www.bing.com/')
    
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(router)