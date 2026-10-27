# функция для отправки сообщений о сегодняшних уроках будет запускать себя раз в день
import asyncio
import httpx
from datetime import datetime,timedelta

from aiogram.enums import parse_mode
from dotenv import load_dotenv
import os
load_dotenv()
API_URL = os.getenv("API_URL").rstrip("/")
async def send_reminder(bot):
    while True:
        now = datetime.now()
        target = now.replace(hour=00, minute=36, second=0, microsecond=0)
        if now > target:
            target += timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(f"{API_URL}/lessons/today")
                lessons = res.json()



                for lesson in lessons:
                    for user in lesson.get('users', []):
                        # Теперь явно ищем user_id
                        chat_id = user.get('user_id')
                        name = user.get('name', 'Ученик')

                        if not chat_id:
                            print(f"Не найден user_id у пользователя: {user}")
                            continue

                        await bot.send_message(
                            chat_id=chat_id,
                            text=(
                                f"📢 Привет, {name}!\n\n"
                                f"Сегодня состоится занятие: <b>{lesson.get('title')}</b> 📚\n"
                                f"Вот ссылка для подключения: {lesson.get('link')}"
                            ),
                            parse_mode='HTML'
                        )
        except Exception as e:
            print('Ошибка',e)

