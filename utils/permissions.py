from database.crud import get_all_users
from aiogram import types

# Проверка, является ли пользователь админом
def is_admin(user_id):
    users = get_all_users()
    for u in users:
        if u[0] == user_id and u[2] == 'admin' and u[3] == 1:
            return True
    return False

# Декоратор для проверки прав администратора
from functools import wraps

def admin_required(handler):
    @wraps(handler)
    async def wrapper(event, *args, **kwargs):
        user_id = getattr(getattr(event, 'from_user', None), 'id', None)
        if not is_admin(user_id):
            if hasattr(event, 'answer'):
                await event.answer("⛔ Нет доступа", show_alert=True)
            elif hasattr(event, 'message') and hasattr(event.message, 'answer'):
                await event.message.answer("⛔ Нет доступа")
            return
        return await handler(event, *args, **kwargs)
    return wrapper 