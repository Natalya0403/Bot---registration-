from aiogram.fsm.state import StatesGroup, State

class Registration(StatesGroup):
    name = State()


class EditProfile(StatesGroup):
    new_name = State()

class AddLesson(StatesGroup):
    title = State()
    date = State()
    spots = State()
    link = State()

class EditLesson(StatesGroup):
    title = State()
    date = State()
    spots = State()
    link = State()