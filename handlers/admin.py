from aiogram import types
from aiogram.fsm.context import FSMContext
from states.states import AdminPanel, AddUser, BlockUser, DeleteUser, AddCabinetGlobal
from keyboards.keyboards import admin_main_keyboard, admin_user_select_keyboard, admin_cabinet_access_keyboard, admin_clients_keyboard, admin_client_cabinets_keyboard
from database.crud import get_all_users, add_user, find_user_by_username, set_user_active, delete_user, log_admin_action, get_admin_logs, get_user_permissions, set_user_permission, get_all_cabinets, add_global_cabinet, get_user_cabinets
from utils.permissions import is_admin, admin_required

# Проверка роли (можно вынести в отдельный декоратор)
# def is_admin(user_id):
#     users = get_all_users()
#     for u in users:
#         if u[0] == user_id and u[2] == 'admin' and u[3] == 1:
#             return True
#     return False

@admin_required
async def admin_menu(event, state: FSMContext):
    # event может быть Message или CallbackQuery
    if isinstance(event, types.CallbackQuery):
        user_id = event.from_user.id
        message = event.message
        await event.answer()
    else:
        user_id = event.from_user.id
        message = event
    print("Ваш user_id:", user_id)
    print("Все пользователи:", get_all_users())
    await message.answer(f"Ваш user_id: {user_id}")
    # if not is_admin(user_id):
    #     await message.answer("⛔ Нет доступа")
    #     return
    await state.set_state(AdminPanel.main)
    await message.answer("🛠️ Админ-панель:", reply_markup=admin_main_keyboard())

@admin_required
async def admin_list(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    users = get_all_users()
    text = "👤 <b>Список клиентов:</b>\n"
    for u in users:
        status = "✅" if u[3] else "🚫"
        role = "(админ)" if u[2] == 'admin' else ""
        text += f"{status} @{u[1]} {role}\n"
    await callback.message.edit_text(text, reply_markup=admin_main_keyboard(), parse_mode="HTML")

@admin_required
async def admin_add(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AddUser.username)
    await callback.message.edit_text("Введите username клиента (без @):")

async def admin_add_username(msg: types.Message, state: FSMContext):
    username = msg.text.strip().lstrip('@')
    # Здесь можно получить user_id только если пользователь уже писал боту
    user = find_user_by_username(username)
    if user:
        await msg.answer("Пользователь уже есть в базе.")
        return
    # В реальном боте — отправить пользователю приглашение, чтобы он написал боту, и только после этого добавить
    await msg.answer("Попросите пользователя сначала написать боту, чтобы его можно было добавить по username.")
    await state.clear()

@admin_required
async def admin_block(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(BlockUser.username)
    await callback.message.edit_text("Введите username клиента для блокировки/разблокировки:")

async def admin_block_username(msg: types.Message, state: FSMContext):
    username = msg.text.strip().lstrip('@')
    user = find_user_by_username(username)
    if not user:
        await msg.answer("Пользователь не найден.")
        await state.clear()
        return
    user_id, username, role, is_active = user
    set_user_active(user_id, 0 if is_active else 1)
    log_admin_action(msg.from_user.id, 'block' if is_active else 'unblock', user_id, username)
    await msg.answer(f"Пользователь @{username} {'заблокирован' if is_active else 'разблокирован'}.")
    await state.clear()

@admin_required
async def admin_delete(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(DeleteUser.username)
    await callback.message.edit_text("Введите username клиента для удаления:")

async def admin_delete_username(msg: types.Message, state: FSMContext):
    username = msg.text.strip().lstrip('@')
    user = find_user_by_username(username)
    if not user:
        await msg.answer("Пользователь не найден.")
        await state.clear()
        return
    user_id, username, role, is_active = user
    # Защита: нельзя удалить себя, если вы единственный админ
    all_users = get_all_users()
    admin_count = sum(1 for u in all_users if u[2] == 'admin' and u[3] == 1)
    if role == 'admin' and admin_count <= 1:
        await msg.answer("❗️ Нельзя удалить последнего админа!")
        await state.clear()
        return
    if user_id == msg.from_user.id:
        await msg.answer("❗️ Нельзя удалить самого себя через админ-панель!")
        await state.clear()
        return
    delete_user(user_id)
    log_admin_action(msg.from_user.id, 'delete', user_id, username)
    await msg.answer(f"Пользователь @{username} удалён.")
    await state.clear()

@admin_required
async def admin_logs(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    logs = get_admin_logs()
    text = "<b>Логи действий:</b>\n"
    for l in logs:
        admin_id, action, target_user_id, target_username, ts = l
        text += f"{ts}: admin_id={admin_id} {action} @{target_username} (id={target_user_id})\n"
    await callback.message.edit_text(text, reply_markup=admin_main_keyboard(), parse_mode="HTML")

async def admin_back(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("Выход из админ-панели.")

@admin_required
async def admin_access_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    users = [u for u in get_all_users() if u[2] == 'client' and u[3] == 1]
    await callback.message.edit_text("Выберите пользователя:", reply_markup=admin_user_select_keyboard(users))

@admin_required
async def admin_access_user(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = getattr(callback, 'data', None)
    user_id = int(data.split('_')[-1])
    cabinets = get_all_cabinets()  # только существующие кабинеты
    permissions = get_user_permissions(user_id)
    await callback.message.edit_text(f"Доступ к кабинетам для пользователя {user_id}:", reply_markup=admin_cabinet_access_keyboard(user_id, cabinets, permissions))

@admin_required
async def admin_access_toggle(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = getattr(callback, 'data', None)
    parts = data.split('_')
    user_id = int(parts[3])
    cabinet_id = int(parts[4])
    permissions = get_user_permissions(user_id)
    new_access = not permissions.get(cabinet_id, False)
    set_user_permission(user_id, cabinet_id, new_access)
    cabinets = get_all_cabinets()
    permissions = get_user_permissions(user_id)
    await callback.message.edit_text(f"Доступ к кабинетам для пользователя {user_id}:", reply_markup=admin_cabinet_access_keyboard(user_id, cabinets, permissions))

@admin_required
async def admin_add_cabinet(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AddCabinetGlobal.name)
    await callback.message.edit_text("Введите название нового кабинета:")

async def admin_add_cabinet_finish(msg: types.Message, state: FSMContext):
    name = msg.text.strip()
    add_global_cabinet(name)
    await msg.answer(f"Кабинет '{name}' добавлен!", reply_markup=admin_main_keyboard())
    await state.clear() 