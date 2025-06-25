from aiogram.fsm.state import StatesGroup, State

class AddCabinet(StatesGroup):
    """Состояния для добавления нового кабинета"""
    name = State()
    client_id = State()
    secret_id = State()
    advertiser_id = State()

class RenameCabinet(StatesGroup):
    """Состояния для переименования кабинета"""
    cabinet_index = State()
    new_name = State()

class DeleteCabinet(StatesGroup):
    """Состояния для удаления кабинета"""
    cabinet_index = State()
    confirm = State()

class AddTrigger(StatesGroup):
    type = State()
    threshold = State()

class EditTrigger(StatesGroup):
    value = State()

class AdminPanel(StatesGroup):
    main = State()

class AddUser(StatesGroup):
    username = State()

class BlockUser(StatesGroup):
    username = State()

class DeleteUser(StatesGroup):
    username = State()

class ViewLogs(StatesGroup):
    pass

class AddCabinetGlobal(StatesGroup):
    name = State() 