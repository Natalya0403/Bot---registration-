from datetime import date
from typing import List, Optional, Dict, Any

from sqlalchemy import asc, desc
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from db.connect import async_session
from db.models import User, Lesson


# --- ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЕМ ---

async def create_user(user_data: UserModel):
  async with async_session() as session:
    stmt = select(User).where(User.user_id == user_data.user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    # В зависимости от типа поля birth в вашей модели БД:
    # 1. Если в БД поле birth это String: конвертируем обратно в строку ISO "YYYY-MM-DD"
    #    birth_val = user_data.birth.strftime("%Y-%m-%d") (или "%d.%m.%Y")
    # 2. Если в БД поле birth это Date: передаем как есть (user_data.birth)

    if user:
      # Обновляем существующего пользователя
      user.name = user_data.name
      user.email = user_data.email
      user.city = user_data.city
      user.birth = str(user_data.birth)  # Превращаем date обратно в str, если в БД это String
      user.phone = user_data.phone
    else:
      # Создаем нового пользователя
      user = User(
          user_id=user_data.user_id,
          name=user_data.name,
          email=user_data.email,
          city=user_data.city,
          birth=str(
              user_data.birth
          ),  # Превращаем date обратно в str, если в БД это String
          phone=user_data.phone,
      )

    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


# --- ФУНКЦИИ ДЛЯ РАБОТЫ С УРОКАМИ ---

async def create_lesson(title: str, date_obj: date, spots: int, link: str = ''):
    async with async_session() as session:
        lesson = Lesson(title=title, date=date_obj, spots=spots, link=link)
        session.add(lesson)
        await session.commit()
        await session.refresh(lesson)
        return lesson


async def get_today_lessons() -> List[Dict[str, Any]]:
    today = date.today()
    async with async_session() as session:
        result = await session.execute(
            select(Lesson)
            .options(selectinload(Lesson.users))
            .where(Lesson.date == today)
        )
        lessons = result.scalars().all()

        data = []
        for lesson in lessons:
            users = [{"name": u.name, "user_id": u.user_id} for u in lesson.users]
            data.append({
                "title": lesson.title,
                "link": lesson.link,
                "users": users
            })
        return data


# --- АДМИН-ПАНЕЛЬ ---

async def get_all_lessons_with_users():
    async with async_session() as session:
        result = await session.execute(
            select(Lesson)
            .options(selectinload(Lesson.users))
            .order_by(Lesson.date)
        )
        lessons = result.scalars().all()

        if not lessons:
            return []

        lessons_data = []
        for lesson in lessons:
            users = [{"name": u.name, "user_id": u.user_id, "email": u.email} for u in lesson.users]
            lessons_data.append({
                'id': lesson.id,  # 👈 Обязательно передаем ID для кнопок в боте
                'title': lesson.title,
                'date': lesson.date,
                'link': lesson.link,
                'spots': lesson.spots,
                'users': users
            })
        return lessons_data
# Получение одного урока по его ID (для детального просмотра)
async def get_lesson_by_id(lesson_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(Lesson)
            .options(selectinload(Lesson.users))
            .where(Lesson.id == lesson_id)
        )
        lesson = result.scalar_one_or_none()

        if not lesson:
            return None

        users = [{"name": u.name, "user_id": u.user_id, "email": u.email} for u in lesson.users]
        return {
            'id': lesson.id,
            'title': lesson.title,
            'date': lesson.date,
            'link': lesson.link,
            'spots': lesson.spots,
            'users': users
        }
# Удаление урока админом
async def delete_lesson_by_id(lesson_id: int):
    async with async_session() as session:
        result = await session.execute(select(Lesson).where(Lesson.id == lesson_id))
        lesson = result.scalar_one_or_none()

        if not lesson:
            return False

        await session.delete(lesson)
        await session.commit()
        return True

async def get_all_lesson():
    async with async_session() as session:
        result = await session.execute(select(Lesson).order_by(Lesson.date))
        return result.scalars().all()


# Исправлено: добавлен возврат результата
async def get_lesson_by_date(date_obj: date):
    async with async_session() as session:
        result = await session.execute(
            select(Lesson)
            .options(selectinload(Lesson.users))
            .where(Lesson.date == date_obj)
        )
        return result.scalars().all()


# --- ЗАПИСЬ И ОТМЕНА ЗАНЯТИЙ ---

async def reduce_spots(lesson_id: int, user_id: int) -> bool:
  async with async_session() as session:
    # 1. Находим пользователя по Telegram user_id и загружаем его уроки
    result = await session.execute(
        select(User)
        .options(selectinload(User.lessons))
        .where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
      return False

    # 2. Находим конкретный урок по его уникальному lesson_id
    result = await session.execute(
        select(Lesson)
        .options(selectinload(Lesson.users))
        .where(Lesson.id == lesson_id)
    )
    lesson = result.scalar_one_or_none()

    # Если урок не найден или нет свободных мест
    if not lesson or lesson.spots <= 0:
      return False

    # 3. Проверка повторной записи
    if lesson in user.lessons:
      return False

    # 4. Уменьшаем количество мест и добавляем запись
    lesson.spots -= 1
    user.lessons.append(lesson)

    await session.commit()
    return True


async def cancel_user_lesson(user_id: int, date_obj: date) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .options(selectinload(User.lessons))
            .where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return False

        for lesson in user.lessons:
            if lesson.date == date_obj:
                user.lessons.remove(lesson)
                lesson.spots += 1
                await session.commit()
                return True

        return False


# --- ЛИЧНЫЙ КАБИНЕТ И ПРОФИЛЬ ---

async def get_user_by_id(user_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .options(selectinload(User.lessons))
            .where(User.user_id == user_id)
        )
        return result.scalar_one_or_none()


async def update_user(user_id: int, field: str, value: str):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            return None

        # Проверяем, что обновляемое поле существует у пользователя
        if hasattr(user, field):
            setattr(user, field, value)
            await session.commit()
            await session.refresh(user)

        return user

    