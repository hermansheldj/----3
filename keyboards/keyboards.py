from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional
from database.crud import get_user_cabinets, get_accessible_cabinets, get_all_users
import asyncio
from utils.permissions import is_admin

async def cabinets_keyboard(user_id: int, active_idx: Optional[int] = None) -> InlineKeyboardMarkup:
    """Создает клавиатуру с кабинетами пользователя (только из базы)"""
    if is_admin(user_id):
        cabs = await get_user_cabinets(user_id)
    else:
        cabs = await get_accessible_cabinets(user_id)
    kb = []
    for idx, cab in enumerate(cabs):
        name = getattr(cab, 'name', None) or getattr(cab, 'name', None) or 'Без названия'
        text = f"{name}"
        if idx == (active_idx if active_idx is not None else -1):
            text = "▶️ " + text
        kb.append([InlineKeyboardButton(
            text=text,
            callback_data=f"select_{cab.id}"
        )])
    kb.append([
        InlineKeyboardButton(text="➕ Добавить", callback_data="add"),
    ])
    kb.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def cabinet_detail_keyboard(cabinet_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для детального просмотра кабинета"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"rename_{cabinet_id}"),
         InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_{cabinet_id}")],
        [InlineKeyboardButton(text="📊 Баланс", callback_data=f"balance_{cabinet_id}")],
        [InlineKeyboardButton(text="🔔 Добавить триггер", callback_data=f"add_trigger_{cabinet_id}")],
        [InlineKeyboardButton(text="🔔 Мои триггеры", callback_data=f"show_triggers_{cabinet_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="cabinets")]
    ])

def cancel_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопкой отмены"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

def confirm_keyboard(action: str, item_id: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру подтверждения действия"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{action}_{item_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data="cancel")
        ]
    ])

def main_menu_keyboard(is_admin=False):
    kb = [
        [InlineKeyboardButton(text="🏢 Кабинеты", callback_data="cabinets_menu")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="statistics_menu")],
    ]
    if is_admin:
        kb.append([InlineKeyboardButton(text="🛠️ Админ-панель", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def cabinets_menu_keyboard(user_id, cabinets):
    kb = []
    for idx, cab in enumerate(cabinets):
        kb.append([InlineKeyboardButton(text=cab['name'], callback_data=f"cabinet_{idx}")])
    kb.append([InlineKeyboardButton(text="➕ Добавить", callback_data="add_cabinet")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def statistics_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])

def trigger_type_keyboard(cabinet_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Основной", callback_data=f"trigger_type_real_{cabinet_id}")],
        [InlineKeyboardButton(text="CPA", callback_data=f"trigger_type_cpa_{cabinet_id}")],
        [InlineKeyboardButton(text="Общий", callback_data=f"trigger_type_total_{cabinet_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

def trigger_list_keyboard(cabinet_id: int, triggers: list) -> InlineKeyboardMarkup:
    kb = []
    for trig in triggers:
        tname = {'real': 'Основной', 'cpa': 'CPA', 'total': 'Общий'}.get(trig['trigger_type'], trig['trigger_type'])
        kb.append([
            InlineKeyboardButton(
                text=f"{tname}: {trig['threshold']:.2f} ₽ ✏️ Изменить",
                callback_data=f"edit_trigger_{cabinet_id}_{trig['trigger_type']}"
            ),
            InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=f"delete_trigger_{cabinet_id}_{trig['trigger_type']}"
            ),
            InlineKeyboardButton(
                text="⏰ Частота уведомлений",
                callback_data=f"set_interval_menu_{cabinet_id}_{trig['trigger_type']}"
            )
        ])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"select_{cabinet_id}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def notification_interval_keyboard(trigger_type: str, cabinet_id: int, current_value: int) -> InlineKeyboardMarkup:
    intervals = [
        (0, "❌ Без повторений"),
        (5, "5 минут"),
        (15, "15 минут"),
        (30, "30 минут"),
        (60, "1 час"),
        (180, "3 часа"),
        (360, "6 часов"),
        (720, "12 часов"),
        (1440, "24 часа")
    ]
    kb = []
    for val, text in intervals:
        if val == current_value:
            text = f"✅ {text}"
        kb.append([InlineKeyboardButton(text=text, callback_data=f"set_interval_{cabinet_id}_{trigger_type}_{val}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"show_triggers_{cabinet_id}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Список клиентов", callback_data="admin_list")],
        [InlineKeyboardButton(text="➕ Добавить клиента", callback_data="admin_add")],
        [InlineKeyboardButton(text="🚫 Заблокировать/разблокировать", callback_data="admin_block")],
        [InlineKeyboardButton(text="🗑 Удалить клиента", callback_data="admin_delete")],
        [InlineKeyboardButton(text="🛡️ Управление доступом", callback_data="admin_access")],
        [InlineKeyboardButton(text="📜 Логи действий", callback_data="admin_logs")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
    ])

def admin_user_select_keyboard(users):
    kb = []
    for u in users:
        kb.append([InlineKeyboardButton(text=f"@{u[1]}", callback_data=f"admin_access_user_{u[0]}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_cabinet_access_keyboard(user_id, cabinets, permissions):
    kb = []
    if not cabinets:
        kb.append([InlineKeyboardButton(text="Нет активных кабинетов", callback_data="none")])
    else:
        for cab in cabinets:
            checked = '✅' if permissions.get(cab['id'], False) else '❌'
            kb.append([
                InlineKeyboardButton(
                    text=f"{checked} {cab['name']}",
                    callback_data=f"admin_access_toggle_{user_id}_{cab['id']}"
                )
            ])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def request_access_keyboard(user_id: int, username: str):
    """Создает клавиатуру для запроса доступа к боту"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔐 Запросить доступ",
            callback_data=f"request_access_{user_id}"
        )]
    ])

def admin_clients_keyboard(clients):
    """Клавиатура со списком клиентов для управления доступом"""
    kb = [
        [InlineKeyboardButton(text=f"@{c[1]}", callback_data=f"admin_manage_client_{c[0]}")]
        for c in clients
    ]
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_client_cabinets_keyboard(client_id, cabinets, permissions):
    """Клавиатура со списком кабинетов для управления доступом клиента"""
    kb = []
    for cab in cabinets:
        has_access = permissions.get(cab['id'], False)
        mark = '✅' if has_access else '⛔️'
        kb.append([
            InlineKeyboardButton(
                text=f"{mark} {cab['name']}",
                callback_data=f"admin_toggle_cabinet_{client_id}_{cab['id']}"
            )
        ])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_manage_clients")])
    return InlineKeyboardMarkup(inline_keyboard=kb) 