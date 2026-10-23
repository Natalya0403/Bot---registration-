import logging
import re
import os
import json
from pathlib import Path
import httpx
from dotenv import load_dotenv

from aiogram import Router, F
from aiogram.types import (Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton,
                           CallbackQuery,InlineKeyboardButton, InlineKeyboardMarkup,
                           ReplyKeyboardRemove)
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, BaseFilter
from project.forms import Registration, EditProfile, AddLesson



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
PHOTO_PATH = BASE_DIR / "media" / "foto.jpg"

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
            caption='👋 Привет! Это бот для записи на занятие в школу программирования IT_Start.\n\nЧтобы зарегистрироваться ответьте на несколько вопросов.\n\nПоехали! Как вас зовут?',
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
    await message.answer(f'🤝 Отлично, {name}!\nТеперь введи свой email:', reply_markup=cancel_keyboard)
    await state.set_state(Registration.email)


@router.message(Registration.email, ~F.text.startswith("/"))
async def get_email(message: Message, state: FSMContext):
    email = message.text.strip()
    if '@' not in email or '.' not in email:
        await message.answer('⚠️ Это не похоже на email. Попробуйте еще раз.', reply_markup=cancel_keyboard)
        return
    await state.update_data(email=email)
    await message.answer('🏙️ Супер! Из какого ты города?', reply_markup=cancel_keyboard)
    await state.set_state(Registration.city)


@router.message(Registration.city, ~F.text.startswith("/"))
async def get_city(message: Message, state: FSMContext):
    city = message.text.strip()
    await state.update_data(city=city)
    await message.answer(
        '🎂 Спасибо!\nОсталось еще немного...\nКогда у тебя день рождения?\nВведите дату в формате: 01.01.2000', reply_markup=cancel_keyboard
    )
    await state.set_state(Registration.birth)


@router.message(Registration.birth, ~F.text.startswith("/"))
async def get_birth(message: Message, state: FSMContext):
    birth = message.text.strip()
    if len(birth) != 10 or birth.count('.') != 2:
        await message.answer('📅 Введите дату рождения в формате: 01.01.2000', reply_markup=cancel_keyboard)
        return
    await state.update_data(birth=birth)

    await message.answer('📱 И финальный шаг!\nВведите пожалуйста номер телефона:', reply_markup=cancel_keyboard)
    await state.set_state(Registration.phone)


@router.message(Registration.phone, ~F.text.startswith("/"))
async def get_phone(message: Message, state: FSMContext):
    phone_raw = message.text.strip()
    clean_phone = re.sub(r'\D', '', phone_raw)

    if len(clean_phone) < 10 or len(clean_phone) > 15:
        await message.answer('❌ Введите корректный номер телефона', reply_markup=cancel_keyboard)
        return

    await state.update_data(phone=clean_phone)

    # Получаем скомпонованный словарь из FSM
    user_data = await state.get_data()

    summary = (
        "🔎 Проверь данные перед регистрацией:\n\n"
        f"👤 Имя: {user_data['name']}\n"
        f"📧 Email: {user_data['email']}\n"
        f"🏙️ Город: {user_data['city']}\n"
        f"🎂 Дата рождения: {user_data['birth']}\n"
        f"📞 Телефон: {user_data['phone']}\n\n"
        "✅ Всё верно?"
    )

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Да, всё верно ✅")],
            [KeyboardButton(text="Заполнить заново ❌")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(summary, reply_markup=keyboard)
    await state.set_state(Registration.confirm)


@router.message(Registration.confirm)
async def get_confirm(message: Message, state: FSMContext):
    if message.text == 'Да, всё верно ✅':
        user_data = await state.get_data()
        user_data['user_id'] = message.from_user.id

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(f'{API_URL}/user/add', json=user_data)

                if response.status_code in (200, 201):
                    await message.answer('🎉 Спасибо за регистрацию! Мы с вами свяжемся.',
                                         reply_markup=ReplyKeyboardRemove())
                    await state.clear()

                elif response.status_code == 422:
                    # Ловим ошибку валидации Pydantic с бэкенда
                    try:
                        err_data = response.json()
                        detail = err_data.get('detail', 'Неверный формат данных.')
                    except Exception:
                        detail = 'Проверьте правильность введенных данных.'

                    await message.answer(
                        f'⚠️ Ошибка проверки данных: {detail}\n\nПожалуйста, начните регистрацию заново с команды /start',
                        reply_markup=ReplyKeyboardRemove()
                    )
                    await state.clear()

                else:
                    await message.answer(f'⚠️ Ошибка сервера ({response.status_code}). Попробуйте позже.',
                                         reply_markup=ReplyKeyboardRemove())
                    await state.clear()

            except httpx.RequestError:
                await message.answer('⚠️ Не удалось связаться с сервером API. Проверьте, запущен ли FastAPI.',
                                     reply_markup=ReplyKeyboardRemove())
                await state.clear()

    elif message.text == 'Заполнить заново ❌':
        await message.answer("Окей! Давай начнём заново 🌀\nНапиши своё имя:", reply_markup=cancel_keyboard)
        await state.set_state(Registration.name)
    else:
        # Если пользователь написал что-то постороннее на этапе подтверждения
        await message.answer("Пожалуйста, выберите вариант с помощью кнопок ниже 👇")

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
            f"<b>Email:</b> {user['email']}\n"
            f"<b>Город:</b> {user['city']}\n"
            f"<b>Дата рождения:</b> {user['birth']}\n"
            f"<b>Телефон:</b> {user['phone']}\n"
        )
        lesson_buttons = []
        if user.get('lessons'):
            profile_text += '\n<b>🗓 Записи на занятия:</b>\n'
            for lesson in user['lessons']:
                profile_text += f"• {lesson['date']} — {lesson['title']}\n"
                lesson_buttons.append([InlineKeyboardButton(text=f"❌ Отменить: {lesson['title']}", callback_data=f"cancel_lesson|{lesson['date']}")
                                       ])
        else:
            profile_text +=f'\n🗓 Вы пока не записаны на занятия.'

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✏️ Редактировать', callback_data="edit_profile")]]+
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
@router.callback_query(F.data == "edit_profile")
async def choose_field(callback: CallbackQuery):
    buttons = [
        [InlineKeyboardButton(text="Имя", callback_data="edit_field|name")],
        [InlineKeyboardButton(text="Email", callback_data="edit_field|email")],
        [InlineKeyboardButton(text="Город", callback_data="edit_field|city")],
        [InlineKeyboardButton(text="Дата рождения", callback_data="edit_field|birth")],
        [InlineKeyboardButton(text="Телефон", callback_data="edit_field|phone")],
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.answer('Что вы хотите изменить?', reply_markup=kb)
    await callback.answer()


# Описываем читаемые названия полей в отдельном словаре
FIELD_NAMES = {
    "name": "имя",
    "email": "email",
    "city": "город",
    "birth": "дату рождения",
    "phone": "номер телефона",
}


@router.callback_query(F.data.startswith("edit_field"))
async def edit_field(callback: CallbackQuery, state: FSMContext):
    # Разделяем Callback Data (ожидается формат "edit_field|name")
    parts = callback.data.split("|")
    if len(parts) < 2:
        await callback.answer("Ошибка: неверный формат данных", show_alert=True)
        return

    field = parts[1]
    await state.update_data(field=field)

    target_name = FIELD_NAMES.get(field, 'новое значение')

    await callback.message.answer(f'Введите новое значение для поля ({target_name}):')
    await state.set_state(EditProfile.new_value)
    await callback.answer()


@router.message(EditProfile.new_value)
async def save_new_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get('field')

    if not field:
        await message.answer(
            'Произошла ошибка сессии. Пожалуйста, выберите поле заново.',
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()
        return

    value = message.text.strip() if message.text else ''
    user_id = message.from_user.id

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # 1. Получаем текущий профиль
            res_get = await client.get(f'{API_URL}/users/{user_id}')
            if res_get.status_code != 200:
                await message.answer('Не удалось получить данные профиля.', reply_markup=ReplyKeyboardRemove())
                await state.clear()
                return

            user_data = res_get.json()
            user_data[field] = value
            user_data['user_id'] = user_id

            # 2. Отправляем обновленную пачку данных
            res_put = await client.put(f'{API_URL}/users/{user_id}', json=user_data)

            if res_put.status_code == 200:
                await message.answer('🎉 Профиль успешно обновлен!', reply_markup=ReplyKeyboardRemove())
                await state.clear()

            elif res_put.status_code == 422:
                # Пытаемся забрать детальный текст ошибки от Pydantic/FastAPI
                try:
                    err_data = res_put.json()
                    detail = err_data.get('detail', 'Неверный формат данных.')
                except Exception:
                    detail = 'Проверьте правильность введенных данных.'

                # Выводим ошибку, но состояние НЕ очищаем (!),
                # чтобы пользователь мог сразу отправить правильный вариант
                await message.answer(
                    f'⚠️ Ошибка проверки: {detail}\n\nПожалуйста, введите корректное значение заново:',
                    reply_markup=cancel_keyboard
                )

            else:
                await message.answer('❌ Не удалось обновить профиль.', reply_markup=ReplyKeyboardRemove())
                await state.clear()

        except httpx.RequestError:
            await message.answer('⚠️ Ошибка соединения с сервером.', reply_markup=ReplyKeyboardRemove())
            await state.clear()
# Admin панель===============================================================================
# Admin панель ===============================================================================

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


# 2. Детальная карточка выбранного урока + список участников
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

    text = (
        f"<b>📅 {lesson['title']} — {lesson['date']}</b>\n"
        f"🪑 Доступно мест: {lesson['spots']}\n"
        f"🔗 Ссылка: {lesson.get('link') or 'нет'}\n\n"
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
        [InlineKeyboardButton(text="❌ Удалить этот урок", callback_data=f"admin_delete_lesson:{lesson['id']}")],
        [InlineKeyboardButton(text="« Назад к списку уроков", callback_data="admin_check")]
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


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


