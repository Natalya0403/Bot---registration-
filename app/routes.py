from datetime import date
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from db.crud import (
    create_user,
    create_lesson,
    reduce_spots,
    get_all_lesson,
    get_user_by_id,
    update_user,
    cancel_user_lesson,
    get_today_lessons,
    get_lessons_with_users,
)

router = APIRouter()


# --- Pydantic Схемы ---

class UserModel(BaseModel):
    name: str = Field(..., min_length=2, max_length=20)
    email: str = Field(..., min_length=5)
    city: str
    birth: str
    phone: str
    user_id: int


class LessonCreate(BaseModel):
    title: str
    date: date
    spots: int
    link: str


class CancelLesson(BaseModel):
    user_id: int
    date: date


# --- Эндпоинты Пользователей и Уроков ---

@router.post("/user/add")
async def user_add(data: UserModel):
    return await create_user(
        data.name, data.email, data.city, data.birth, data.phone, data.user_id
    )


@router.post("/lesson/add")
async def lesson_add(data: LessonCreate):
    return await create_lesson(data.title, data.date, data.spots, data.link)


@router.get("/lessons")
async def get_lessons():
    return await get_all_lesson()


@router.get("/lessons/today")
async def today_lessons():
    return await get_today_lessons()


# --- Для админ-панели ---

@router.get("/admin/lesson/{lesson_date}")
async def admin_lesson_date(lesson_date: date):
    lesson = await get_lessons_with_users(lesson_date)
    if lesson:
        return {"status": "ok", "lesson": lesson}
    return {"status": "fail"}


# --- Запись и Отмена ---

@router.post("/lesson/register/{lesson_date}/{user_id}")
async def register_to_lesson(lesson_date: date, user_id: int):
    res = await reduce_spots(lesson_date, user_id)
    if res:
        return {'status': 'ok', 'message': 'Запись успешно создана'}
    return {'status': 'fail', 'message': 'Запись не успешна'}


@router.post("/lesson/cancel")
async def cancel_lesson(data: CancelLesson):
    res = await cancel_user_lesson(user_id=data.user_id, date_obj=data.date)
    if res:
        return {'status': 'ok', 'message': 'Запись успешно отменена'}
    return {'status': 'fail', 'message': 'Не удалось отменить запись'}


# --- Профиль пользователя и редактирование ---

@router.get("/users/{user_id}")
async def get_user_id(user_id: int):
    user = await get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    lessons_data = [
        {'title': l.title, 'date': l.date.isoformat()}
        for l in getattr(user, 'lessons', [])
    ]

    return {
        "name": user.name,
        "email": user.email,
        "city": user.city,
        "birth": user.birth,
        "phone": user.phone,
        "lessons": lessons_data
    }


@router.put("/users/{user_id}")
async def edit_user(user_id: int, data: Dict[str, Any]):
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Тело запроса не должно быть пустым"
        )

    field, value = list(data.items())[0]
    user = await update_user(user_id, field, value)

    if not user:
        return {'status': 'fail'}
    return {'status': 'ok'}