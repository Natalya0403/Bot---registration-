import re
import os
import json
from pathlib import Path
import httpx
from dotenv import load_dotenv

from aiogram import Router, F
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery,InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, BaseFilter
from project.forms import Registration, EditProfile, AddLesson
from aiogram3_calendar import SimpleCalendar


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
@router.message(Command('start'))
async def send_welcome(message: Message, state: FSMContext):
    await state.clear()  # Сбрасываем старые состояния при /start

    if PHOTO_PATH.exists():
        foto = FSInputFile(PHOTO_PATH)
        await message.answer_photo(
            photo=foto,
            caption='👋 Привет! Это бот для записи на занятие в школу программирования IT_School_niv.\n\nЧтобы зарегистрироваться ответьте на несколько вопросов.\n\nПоехали! Как вас зовут?'
        )
    else:
        await message.answer(
            '👋 Привет! Это бот для записи на занятие в школу программирования IT_School_niv.\n\nЧтобы зарегистрироваться ответьте на несколько вопросов.\n\nПоехали! Как вас зовут?')

    await state.set_state(Registration.name)


@router.message(Registration.name)
async def get_name(message: Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(name=name)
    await message.answer(f'🤝 Отлично, {name}!\nТеперь введи свой email:')
    await state.set_state(Registration.email)


@router.message(Registration.email)
async def get_email(message: Message, state: FSMContext):
    email = message.text.strip()
    if '@' not in email or '.' not in email:
        await message.answer('⚠️ Это не похоже на email. Попробуйте еще раз.')
        return
    await state.update_data(email=email)
    await message.answer('🏙️ Супер! Из какого ты города?')
    await state.set_state(Registration.city)


@router.message(Registration.city)
async def get_city(message: Message, state: FSMContext):
    city = message.text.strip()
    await state.update_data(city=city)
    await message.answer(
        '🎂 Спасибо!\nОсталось еще немного...\nКогда у тебя день рождения?\nВведите дату в формате: 01.01.2000'
    )
    await state.set_state(Registration.birth)


@router.message(Registration.birth)
async def get_birth(message: Message, state: FSMContext):
    birth = message.text.strip()
    if len(birth) != 10 or birth.count('.') != 2:
        await message.answer('📅 Введите дату рождения в формате: 01.01.2000')
        return
    await state.update_data(birth=birth)

    await message.answer('📱 И финальный шаг!\nВведите пожалуйста номер телефона:')
    await state.set_state(Registration.phone)


@router.message(Registration.phone)
async def get_phone(message: Message, state: FSMContext):
    phone_raw = message.text.strip()
    clean_phone = re.sub(r'\D', '', phone_raw)

    if len(clean_phone) < 10 or len(clean_phone) > 15:
        await message.answer('❌ Введите корректный номер телефона')
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
        # Присваиваем результат вызова функции в переменную user_data
        user_data = await state.get_data()
        user_data['user_id'] = message.from_user.id

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(f'{API_URL}/user/add', json=user_data)
                if response.status_code == 200 or response.status_code == 201:
                    await message.answer('🎉 Спасибо за регистрацию! Мы с вами свяжемся.')
                    await state.clear()  # Очищаем FSM после успешной записи
                else:
                    await message.answer(f'⚠️ Ошибка сервера ({response.status_code}). Попробуйте позже.')
            except httpx.RequestError:
                await message.answer('⚠️ Не удалось связаться с сервером API. Проверьте, запущен ли FastAPI.')
    else:

        await message.answer("Окей! Давай начнём заново 🌀\nНапиши своё имя:")
        await state.set_state(Registration.name)
    await state.clear()  # Сбрасываем старый ввод

@router.message(F.text == "/calendar")
async def show_calendar(message: Message):
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{API_URL}/lessons")
        lessons = res.json()

    if not lessons:
        await message.answer("❗ Произошла ошибка, нет уроков!")
        return

    buttons = []
    for lesson in lessons:
        label = f"{lesson['date']} ({lesson['spots']} мест)"
        btn = InlineKeyboardButton(text=label, callback_data=f"choose_date|{lesson['date']}")
        buttons.append([btn])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выберите дату, чтобы записаться на занятие 👇", reply_markup=kb)


@router.callback_query(F.data.startswith("choose_date"))
async def register_on_date(callback: CallbackQuery):
    date_str = callback.data.split("|")[1]
    user_id = callback.from_user.id

    async with httpx.AsyncClient() as client:
        res = await client.post(f"{API_URL}/lesson/register/{date_str}/{user_id}")
        data = res.json()

    if data["status"] == "ok":
        await callback.message.answer("🎉 Вы успешно записались на занятие!")
    else:
        await callback.message.answer("❌ К сожалению, мест на эту дату больше нет.")

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
@router.message(Command("edit_profile"))
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

@router.message(F.data.startswith("edit_field"))
async def edit_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split("|")[1]
    await state.update_data(field=field)
    await callback.message.answer('Введите новое значение?')
    await state.set_state(EditProfile.new_value)
    await callback.answer()

@router.message(EditProfile.new_value)
async def save_new_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data['field']
    value = message.text.strip()

    async with httpx.AsyncClient() as client:
        res = await client.put(f"{API_URL}/users/{message.from_user.id}",json={field: value})

        if res.status_code == 200:
            await message.answer('Вы успешно отредактировали!')
        else:
            await message.answer('К сожалению не удалось. Попробуйте позже')
    await state.clear()

# Admin панель===============================================================================
@router.message(Command("admin"),IsAdmin())
async def admin_panel(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Добавить урок", callback_data="admin_add")],
        [InlineKeyboardButton(text="👥 Кто записан?", callback_data="admin_check")]
    ])
    await message.answer("👨‍💼 Панель администратора",reply_markup=kb)

@router.callback_query(F.data=='admin_add', IsAdmin())
async def admin_add_lesson(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer('Введите название урока')
    await state.set_state(AddLesson.title)
    await callback.answer()
@router.message(AddLesson.title, IsAdmin())
async def add_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer('Введите дату урока(в формате ГГГГ-ММ-ДД)')
    await state.set_state(AddLesson.date)

@router.message(AddLesson.date, IsAdmin())
async def add_date(message: Message, state: FSMContext):
    await state.update_data(date=message.text.strip())
    await message.answer('Сколько мест доступно?')
    await state.set_state(AddLesson.spots)

@router.message(AddLesson.spots, IsAdmin())
async def add_spots(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer('Введите количество мест числом')
        return
    await state.update_data(spots=message.text.strip())
    await message.answer('Добавьте ссылку на урок.')
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


@router.callback_query(F.data == "admin_check", IsAdmin())
async def ask_date(callback: CallbackQuery):
    await callback.message.answer("Введите дату (ГГГГ-ММ-ДД), чтобы узнать, кто записан:")
    await callback.answer()
    await callback.message.delete()


@router.message(F.text.regexp(r"^\d{4}-\d{2}-\d{2}$"), IsAdmin())
async def show_registrations(message: Message):
    date_str = message.text.strip()

    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(f"{API_URL}/admin/lesson/{date_str}")

            # Проверяем успешность ответа сервера
            if res.status_code != 200:
                await message.answer(f"⚠️ Ошибка сервера API ({res.status_code}).")
                return

            data = res.json()

        except httpx.RequestError:
            await message.answer("⚠️ Не удалось связаться с сервером API.")
            return
        except json.decoder.JSONDecodeError:
            await message.answer("⚠️ Получен некорректный ответ от сервера.")
            return

    # Проверяем статус ответа бэкенда
    if data.get("status") != "ok" or not data.get("lesson"):
        await message.answer("❌ Уроков на эту дату не найдено.")
        return

    lessons_list = data["lesson"]  # Это список уроков за указанную дату

    # Проходимся циклом по каждому уроку за этот день
    for lesson in lessons_list:
        users = lesson.get("users", [])

        text = (
            f"<b>📅 {lesson['title']} — {lesson['date']}</b>\n"
            f"🪑 Осталось мест: {lesson['spots']}\n"
            f"🔗 Ссылка: {lesson.get('link') or 'нет'}\n\n"
        )

        if not users:
            text += "👤 Никто не записан."
        else:
            text += "👥 Записанные пользователи:\n"
            for u in users:
                # Безопасно получаем данные пользователя (.get защищает от KeyError)
                name = u.get("name", "Без имени")
                email = u.get("email", "нет email")
                tg_id = u.get("user_id", "—")

                text += f"• <b>{name}</b> (ID: <code>{tg_id}</code>) | {email}\n"

        await message.answer(text, parse_mode="HTML")



