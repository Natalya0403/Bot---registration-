import re
import os
from pathlib import Path
import httpx
from dotenv import load_dotenv

from aiogram import Router, F
from aiogram.types import (Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton,
                           CallbackQuery,InlineKeyboardButton, InlineKeyboardMarkup,
                           ReplyKeyboardRemove)
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, BaseFilter
from forms import Registration, EditProfile, AddLesson, EditLesson
from aiogram.types import LinkPreviewOptions


load_dotenv()

# Проверка что админ это админ
ADMIN_ID = int(os.getenv('ADMIN_ID'))
class IsAdmin(BaseFilter):
    async def __call__(self, obj)->bool:
        return obj.from_user.id == ADMIN_ID

# Безопасное получение API_URL с дефолтным фолбэком
raw_api_url = os.getenv('API_URL', 'http://127.0.0.1:8000')
API_URL = raw_api_url.rstrip('/')

# Точный путь к файлу: project/media/foto.jpg
BASE_DIR = Path(__file__).resolve().parent
PHOTO_PATH = BASE_DIR / "media" / "photo.jpg"

router = Router()

cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Отмена")]],
    resize_keyboard=True
)
# Глобальный хэндлер на отмену (ловит и команду /cancel, и кнопку "❌ Отмена")
@router.message(Command("cancel"))
@router.message(F.text == "❌ Отмена")
async def cancel_registration(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Вы не находитесь в процессе регистрации.", reply_markup=ReplyKeyboardRemove())
        return

    await state.clear()
    await message.answer(
        "❌ Регистрация отменена. Вы можете начать заново командой /start или посмотреть расписание через /calendar.",
        reply_markup=ReplyKeyboardRemove() # Убирает клавиатуру отмены с экрана
    )
@router.message(Command('start'))
async def send_welcome(message: Message, state: FSMContext):
    await state.clear()  # Сбрасываем старые состояния при /start

    if PHOTO_PATH.exists():
        foto = FSInputFile(PHOTO_PATH)
        await message.answer_photo(
            photo=foto,
            caption='👋 Привет! Это бот для записи на занятие в школу программирования <b>IT-Start</b>.\n\nЧтобы зарегистрироваться напишите ваше имя.',
        reply_markup=cancel_keyboard)
    else:
        await message.answer(
            '👋 Привет! Это бот для записи на занятие в школу программирования IT_Start.\n\nЧтобы зарегистрироваться ответьте на несколько вопросов.\n\nПоехали! Как вас зовут?',
            reply_markup=cancel_keyboard  # 👈 Добавили кнопку отмены
        )

    await state.set_state(Registration.name)


@router.message(Registration.name, ~F.text.startswith("/"))
async def get_name(message: Message, state: FSMContext):
    name = message.text.strip()

    # Простейшая проверка на клиенте: хотя бы 2 символа и отсутствие явного мусора
    if len(name) < 2 or not re.match(r"^[А-Яа-яA-Za-zЁё\s\-]+$", name):
        await message.answer(
            '⚠️ Имя должно содержать минимум 2 буквы и состоять только из букв. Попробуйте еще раз:',
            reply_markup=cancel_keyboard
        )
        return

    await state.update_data(name=name)
    data = await state.get_data()
    name = data.get("name")
    user_data = {
        "user_id": message.from_user.id,
        "name": name
        }

    async with httpx.AsyncClient() as client:
        await client.post(f"{API_URL}/user/add", json=user_data)

    await state.clear()
    await message.answer(f"👋 Приятно познакомиться, {name}! Регистрация завершена.\n\n 👉 Нажмите /calendar, чтобы записаться на занятия.")


@router.message(Command("calendar"))
async def show_calendar(message: Message, state: FSMContext):
    await state.clear()# 👈 Сбрасываем любые зависшие состояния FSM

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{API_URL}/lessons")
        lessons = res.json()

    if not lessons:
        await message.answer("❗ Произошла ошибка, нет уроков!")
        return

    buttons = []
    for lesson in lessons:
        label = f"{lesson['title']} | {lesson['date']} ({lesson['spots']} мест)"
        btn = InlineKeyboardButton(
            text=label, callback_data=f"register_lesson:{lesson['id']}"
        )
        buttons.append([btn])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выберите дату, чтобы записаться на занятие 👇", reply_markup=kb)


@router.callback_query(F.data.startswith("register_lesson"))
async def register_on_lesson_id(callback: CallbackQuery):
    # Достаем lesson_id из callback_data (например, "register_lesson:15" -> 15)
    lesson_id= callback.data.split(":")[1]
    user_id = callback.from_user.id

    async with httpx.AsyncClient() as client:
        res = await client.post(f"{API_URL}/lesson/register/{lesson_id}/{user_id}")
        data = res.json()

    if data["status"] == "ok":
        await callback.message.answer("🎉 Вы успешно записались на занятие!",parse_mode="HTML")
    else:
        error_detail = data.get(
            "detail", "К сожалению, мест нет или вы уже записаны."
        )
        await callback.message.edit_text(f"❌ {error_detail}", parse_mode="HTML")

    await callback.answer()

# Личный кабинет + реализация кнопки отменить конкретный урок
@router.message(Command("profile"))
async def profile(message: Message):
    user_id = message.from_user.id

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{API_URL}/users/{user_id}")
        if res.status_code != 200:
            await message.answer('Ошибка при получении')
            return
        user = res.json()
        profile_text = (
            f"<b>👤 Личный кабинет</b>\n\n"
            f"<b>Имя:</b> {user['name']}\n"
            f"───────────────────\n"  # Тонкий разделитель (опционально)
            f"<b>🗓 Записи на занятия:</b>\n"
        )

        lesson_buttons = []
        if user.get('lessons'):
            for lesson in user['lessons']:
                link = lesson.get('link')
                # Прячем длинную ссылку в аккуратную кликабельную фразу
                link_str = f" | 🔗 <a href='{link}'>Перейти</a>" if link else ""

                # Исправлен синтаксис вывода заголовка и даты урока
                profile_text += f"\n<b>{lesson['title']}</b>\n  📅 <i>{lesson['date']}</i>{link_str}\n"

                # Передаем реальную дату урока в callback_data для отмены
                lesson_buttons.append([
                    InlineKeyboardButton(
                        text=f"❌ Отменить: {lesson['title']}",
                        callback_data=f"cancel_lesson|{lesson['date']}"
                    )
                ])
        else:
            profile_text += f"\n<i>Вы пока не записаны на занятия.</i>"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✏️ Редактировать', callback_data="edit_profile")]] +
            lesson_buttons)

        await message.answer(profile_text, reply_markup=keyboard, parse_mode="HTML")
#========================================================================================
@router.callback_query(F.data.startswith("cancel_lesson"))
async def cancel_lesson_callback(callback: CallbackQuery):
    date_str = callback.data.split("|")[1]
    user_id = callback.from_user.id

    async with httpx.AsyncClient() as client:
        res = await client.post(f"{API_URL}/lesson/cancel", json={'user_id': user_id,'date': date_str })
        data = res.json()

    if data["status"] == "ok":
        await callback.message.answer("🎉 Вы успешно отменили запись на занятие!")
    else:
        await callback.message.answer("❌ К сожалению, не удалось.")

    await callback.answer()
#=========================================================================================
# 1. Ловим нажатие кнопки "Редактировать" из профиля
@router.callback_query(F.data == "edit_profile")
async def start_edit_name(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        '✏️ Введите новое имя (минимум 2 символа, только буквы):',
        reply_markup=cancel_keyboard
    )
    await state.set_state(EditProfile.new_name)
    await callback.answer()


# 2. Принимаем новое имя от пользователя
@router.message(EditProfile.new_name, ~F.text.startswith("/"))
async def save_new_name(message: Message, state: FSMContext):
    new_name = message.text.strip()

    # Клиентская валидация (дублирует строгие правила бэкенда)
    if len(new_name) < 2 or not re.match(r"^[А-Яа-яA-Za-zЁё\s\-]+$", new_name):
        await message.answer(
            '⚠️ Имя должно содержать минимум 2 буквы и состоять только из букв. Попробуйте еще раз:',
            reply_markup=cancel_keyboard
        )
        return

    user_id = message.from_user.id
    payload = {"name": new_name}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Отправляем PUT-запрос с новым именем на бэкенд
            res = await client.put(f'{API_URL}/users/{user_id}', json=payload)

            if res.status_code == 200:
                await message.answer('🎉 Имя успешно обновлено!', reply_markup=ReplyKeyboardRemove())
                await state.clear()

            elif res.status_code == 422:
                # Если бэкенд вернул ошибку валидации
                try:
                    err_data = res.json()
                    detail = err_data.get('detail', 'Неверный формат данных.')
                except Exception:
                    detail = 'Проверьте правильность введенных данных.'

                await message.answer(
                    f'⚠️ Ошибка проверки: {detail}\n\nПожалуйста, введите корректное имя заново:',
                    reply_markup=cancel_keyboard
                )

            else:
                await message.answer('❌ Не удалось обновить профиль.', reply_markup=ReplyKeyboardRemove())
                await state.clear()

        except httpx.RequestError:
            await message.answer('⚠️ Ошибка соединения с сервером.', reply_markup=ReplyKeyboardRemove())
            await state.clear()

# Admin панель===============================================================================


@router.message(Command("admin"), IsAdmin())
async def admin_panel(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Добавить урок", callback_data="admin_add")],
        [InlineKeyboardButton(text="👥 Все уроки и записи", callback_data="admin_check")]
    ])
    await message.answer("👨‍💼 Панель администратора", reply_markup=kb)


# --- Добавление урока ---

@router.callback_query(F.data == 'admin_add', IsAdmin())
async def admin_add_lesson(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer('Введите название урока:')
    await state.set_state(AddLesson.title)
    await callback.answer()


@router.message(AddLesson.title, IsAdmin())
async def add_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer('Введите дату урока (в формате ГГГГ-ММ-ДД):')
    await state.set_state(AddLesson.date)


@router.message(AddLesson.date, IsAdmin())
async def add_date(message: Message, state: FSMContext):
    await state.update_data(date=message.text.strip())
    await message.answer('Сколько мест доступно?')
    await state.set_state(AddLesson.spots)


@router.message(AddLesson.spots, IsAdmin())
async def add_spots(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer('Введите количество мест числом:')
        return
    await state.update_data(spots=int(message.text.strip()))
    await message.answer('Добавьте ссылку на урок:')
    await state.set_state(AddLesson.link)


@router.message(AddLesson.link, IsAdmin())
async def add_link(message: Message, state: FSMContext):
    await state.update_data(link=message.text.strip())
    data = await state.get_data()

    async with httpx.AsyncClient() as client:
        res = await client.post(f"{API_URL}/lesson/add", json=data)

        if res.status_code == 200:
            await message.answer("✅ Урок успешно добавлен!")
        else:
            await message.answer("❌ Ошибка при добавлении урока.")

    await state.clear()


# --- Просмотр всех уроков и удаление ---

# 1. Вывод списка всех уроков
@router.callback_query(F.data == "admin_check", IsAdmin())
async def admin_list_lessons(callback: CallbackQuery):
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(f"{API_URL}/admin/lessons/all")
            data = res.json()
        except Exception:
            await callback.message.answer("⚠️ Ошибка связи с сервером.")
            await callback.answer()
            return

    lessons = data.get("lessons", [])
    if not lessons:
        await callback.message.edit_text("📭 Список уроков пуст.")
        await callback.answer()
        return

    buttons = []
    for lesson in lessons:
        btn_text = f"📅 {lesson['title']} | {lesson['date']} (мест: {lesson['spots']})"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"admin_view_lesson:{lesson['id']}")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("📋 Выберите урок, чтобы посмотреть участников или удалить его:", reply_markup=kb)
    await callback.answer()


# 2. Детальная карточка выбранного урока + список участников + функция редактирования урока
@router.callback_query(F.data.startswith("admin_view_lesson"), IsAdmin())
async def admin_view_lesson_detail(callback: CallbackQuery):
    lesson_id = callback.data.split(":")[1]

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{API_URL}/admin/lesson/id/{lesson_id}")
        if res.status_code != 200:
            await callback.answer("Урок не найден или был удален", show_alert=True)
            return
        data = res.json()

    lesson = data.get("lesson")
    users = lesson.get("users", [])
    lesson_link = lesson.get("link")

    # Выносим ссылку на новую строку, чтобы Telegram корректно сгенерировал превью
    link_section = f"\n🔗 Ссылка:\n{lesson_link}" if lesson_link else "\n🔗 Ссылка: нет"

    text = (
        f"<b>📅 {lesson['title']} — {lesson['date']}</b>\n"
        f"🪑 Доступно мест: {lesson['spots']}"
        f"{link_section}\n\n"
    )

    if not users:
        text += "👤 Никто не записан."
    else:
        text += "👥 Записанные пользователи:\n"
        for u in users:
            name = u.get("name", "Без имени")
            email = u.get("email", "нет email")
            tg_id = u.get("user_id", "—")
            text += f"• <b>{name}</b> (ID: <code>{tg_id}</code>) | {email}\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать урок", callback_data=f"admin_edit_lesson:{lesson['id']}")],
        [InlineKeyboardButton(text="❌ Удалить этот урок", callback_data=f"admin_delete_lesson:{lesson['id']}")],
        [InlineKeyboardButton(text="« Назад к списку уроков", callback_data="admin_check")]
    ])

    await callback.message.edit_text(
        text,
        reply_markup=kb,
        parse_mode="HTML",
        link_preview_options=LinkPreviewOptions(is_disabled=False) # Явно разрешаем показ превью
    )
    await callback.answer()
# Запуск процесса редактирования урока

@router.callback_query(F.data.startswith("admin_edit_lesson"), IsAdmin())
async def admin_edit_lesson_start(callback: CallbackQuery, state: FSMContext):
    lesson_id = callback.data.split(":")[1]
    await state.update_data(editing_lesson_id=lesson_id)

    await callback.message.answer("Введите новое название урока:")
    await state.set_state(EditLesson.title)
    await callback.answer()


@router.message(EditLesson.title, IsAdmin())
async def edit_lesson_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("Введите новую дату урока (в формате ГГГГ-ММ-ДД):")
    await state.set_state(EditLesson.date)


@router.message(EditLesson.date, IsAdmin())
async def edit_lesson_date(message: Message, state: FSMContext):
    await state.update_data(date=message.text.strip())
    await message.answer("Сколько доступно мест?")
    await state.set_state(EditLesson.spots)


@router.message(EditLesson.spots, IsAdmin())
async def edit_lesson_spots(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите количество мест числом:")
        return
    await state.update_data(spots=int(message.text.strip()))
    await message.answer("Введите новую ссылку на урок:")
    await state.set_state(EditLesson.link)


@router.message(EditLesson.link, IsAdmin())
async def edit_lesson_link(message: Message, state: FSMContext):
    await state.update_data(link=message.text.strip())
    data = await state.get_data()
    lesson_id = data.pop("editing_lesson_id")

    async with httpx.AsyncClient() as client:
        res = await client.put(f"{API_URL}/admin/lesson/{lesson_id}", json=data)

        if res.status_code == 200:
            await message.answer("✅ Урок успешно обновлен!")
        else:
            await message.answer("❌ Ошибка при обновлении урока.")

    await state.clear()

# 3. Обработчик удаления урока
@router.callback_query(F.data.startswith("admin_delete_lesson"), IsAdmin())
async def admin_delete_lesson_action(callback: CallbackQuery):
    lesson_id = callback.data.split(":")[1]

    async with httpx.AsyncClient() as client:
        res = await client.delete(f"{API_URL}/admin/lesson/{lesson_id}")
        if res.status_code == 200:
            await callback.answer("✅ Урок успешно удален!", show_alert=True)
            # Автоматически обновляем список уроков
            await admin_list_lessons(callback)
        else:
            await callback.answer("❌ Не удалось удалить урок.", show_alert=True)


