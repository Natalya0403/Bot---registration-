from aiogram.fsm.state import StatesGroup, State

class Registration(StatesGroup):
    name = State()
    email = State()
    city = State()
    birth = State()
    phone = State()
    confirm = State()

class EditProfile(StatesGroup):
    field = State()
    new_value = State()

class AddLesson(StatesGroup):
    title = State()
    date = State()
    spots = State()
    link = State()

