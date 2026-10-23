from datetime import date, datetime
from typing import Dict, Any
import re
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

from db.crud import (
    create_user,
    create_lesson,
    reduce_spots,
    get_all_lesson,
    get_user_by_id,
    update_user,
    cancel_user_lesson,
    get_today_lessons,
    get_all_lessons_with_users,
    get_lesson_by_id,
    delete_lesson_by_id
)

router = APIRouter()


# --- Pydantic Схемы ---

class UserModel(BaseModel):
  name: str = Field(
      ...,
      min_length=2,  # Минимум 2 символа
      max_length=50,  # Максимум 50 символов
      pattern=r"^[А-Яа-яA-Za-zA-Яa-яЁё\s\-]+$",  # ТОЛЬКО буквы, пробелы и дефисы
      description="Имя пользователя",
  )
  email: EmailStr = Field(..., description="Электронная почта")
  city: str = Field(
      ..., min_length=2, max_length=50, description="Город проживания"
  )
  birth: date = Field(..., description="Дата рождения в формате ДД.ММ.ГГГГ")
  phone: str = Field(..., description="Номер телефона")
  user_id: int = Field(..., description="Telegram ID пользователя")

  # 1. Валидатор для даты рождения: превращает строку "ДД.ММ.ГГГГ" в объект date
  @field_validator("birth", mode="before")
  @classmethod
  def parse_birth_date(cls, value: Any) -> Any:
    if isinstance(value, str):
      try:
        return datetime.strptime(value.strip(), "%d.%m.%Y").date()
      except ValueError:
        raise ValueError(
            "Дата рождения должна быть в формате ДД.ММ.ГГГГ (например,"
            " 01.01.2000)"
        )
    return value

  # 2. Валидатор для телефона: очищает мусор и проверяет длину
  @field_validator("phone", mode="before")
  @classmethod
  def validate_phone(cls, value: str) -> str:
    if not isinstance(value, str):
      raise ValueError("Телефон должен быть строкой")

    # Убираем всё, кроме цифр (плюсы, скобки, тире, пробелы)
    clean_phone = re.sub(r"\D", "", value)

    if not (10 <= len(clean_phone) <= 15):
      raise ValueError("Номер телефона должен содержать от 10 до 15 цифр.")

    return clean_phone


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
async def add_user_route(user_data: UserModel):
  # Сюда придут ТОЛЬКО очищенные и провалидированные данные!
  user = await create_user(user_data)
  return {"status": "ok", "user_id": user.user_id}


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
    lesson = await get_all_lessons_with_users(lesson_date)
    if lesson:
        return {"status": "ok", "lesson": lesson}
    return {"status": "fail"}

# 1. Получение всех уроков вместе с записанными пользователями
@router.get("/admin/lessons/all")
async def admin_get_all_lessons():
    lessons = await get_all_lessons_with_users()
    return {"status": "ok", "lessons": lessons}


# 2. Получение информации об одном конкретном уроке по его ID
@router.get("/admin/lesson/id/{lesson_id}")
async def admin_get_lesson_by_id(lesson_id: int):
    lesson = await get_lesson_by_id(lesson_id)
    if lesson:
        return {"status": "ok", "lesson": lesson}
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Урок не найден"
    )


# 3. Удаление урока по его ID
@router.delete("/admin/lesson/{lesson_id}")
async def admin_delete_lesson(lesson_id: int):
    success = await delete_lesson_by_id(lesson_id)
    if success:
        return {"status": "ok", "message": "Урок успешно удален"}
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Урок не найден или уже был удален"
    )
# --- Запись и Отмена ---

@router.post("/lesson/register/{lesson_id}/{user_id}")
async def register_to_lesson_route(lesson_id: int, user_id: int):
  """Регистрирует пользователя на урок по уникальному lesson_id."""
  # Вызываем функцию уменьшения мест и создания связи
  success = await reduce_spots(lesson_id, user_id)

  if not success:
    return {
        "status": "error",
        "detail": (
            "Не удалось записаться. Возможно, нет свободных мест, урок не"
            " найден или вы уже записаны."
        ),
    }

  return {"status": "ok"}

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

    # 1. Получаем текущие данные пользователя из БД, чтобы собрать полный объект
    current_user = await get_user_by_id(user_id)
    if not current_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # 2. Собираем полный словарь данных пользователя, заменяя обновляемое поле
    user_dict = {
        "user_id": current_user.user_id,
        "name": current_user.name,
        "email": current_user.email,
        "city": current_user.city,
        "birth": current_user.birth,
        "phone": current_user.phone,
    }

    # Обновляем то поле, которое прислал бот
    field, value = list(data.items())[0]
    if field in user_dict:
        user_dict[field] = value

    # 3. Прогоняем ВСЮ структуру через нашу строгую Pydantic-модель UserModel!
    # Если пользователь ввел цифру вместо имени, Pydantic выбросит ошибку 422 сама.
    try:
        validated_data = UserModel(**user_dict)
    except Exception as e:
            # Pydantic возвращает сложный объект ошибки, превращаем его в читаемый текст
            error_msg = "Неверный формат данных."

            # Проверяем, в каком поле произошла ошибка и пишем понятную причину
            if "name" in str(e):
                error_msg = "Имя должно содержать только буквы и быть длиннее 2 символов."
            elif "phone" in str(e):
                error_msg = "Введите корректный номер телефона (от 10 до 15 цифр)."
            elif "email" in str(e):
                error_msg = "Введите корректный Email адрес."
            elif "city" in str(e):
                error_msg = "Название города указано некорректно."
            elif "birth" in str(e):
                error_msg = "Дата рождения должна быть в формате ДД.ММ.ГГГГ."

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error_msg
            )
    # 4. Если валидация прошла успешно — обновляем поле в базе через CRUD
    user = await update_user(user_id, field, validated_data.model_dump()[field])

    if not user:
        return {'status': 'fail'}
    return {'status': 'ok'}