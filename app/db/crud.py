from datetime import date
from typing import List, Optional, Dict, Any

from sqlalchemy import asc, desc
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from db.connect import async_session
from db.models import User, Lesson


# --- ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЕМ ---

async def create_user(name: str, email: str, city: str, birth: str, phone: str, user_id: int):
    async with async_session() as session:
        stmt = select(User).where(User.user_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            user.name = name
            user.email = email
            user.city = city
            user.birth = birth
            user.phone = phone
        else:
            user = User(
                user_id=user_id,
                name=name,
                email=email,
                city=city,
                birth=birth,
                phone=phone)
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

async def get_lessons_with_users(date_obj: date):
    async with async_session() as session:
        result = await session.execute(
            select(Lesson)
            .options(selectinload(Lesson.users))
            .where(Lesson.date == date_obj)
        )
        lessons = result.scalars().all()

        if not lessons:
            return None

        # Возвращаем список уроков с привязанными пользователями
        lessons_data = []
        for lesson in lessons:
            users = [{"name": u.name, "user_id": u.user_id, "email": u.email} for u in lesson.users]
            lessons_data.append({
                'title': lesson.title,
                'date': lesson.date,
                'link': lesson.link,
                'spots': lesson.spots,
                'users': users
            })
        return lessons_data


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

async def reduce_spots(date_obj: date, user_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .options(selectinload(User.lessons))
            .where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return False

        result = await session.execute(
            select(Lesson).where(Lesson.date == date_obj)
        )
        lesson = result.scalar_one_or_none()

        if not lesson or lesson.spots <= 0:
            return False

        # Проверка повторной записи
        if lesson in user.lessons:
            return False

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