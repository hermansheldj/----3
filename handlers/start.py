from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from keyboards.keyboards import cabinets_keyboard, main_menu_keyboard, request_access_keyboard
from database.crud import get_all_users, get_user_by_id, add_user
from config import ADMIN_ID
from utils.permissions import is_admin

async def start_cmd(msg: types.Message, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()
    
    if not msg.from_user:
        await msg.answer("Ошибка: не удалось определить пользователя.")
        return
        
    user_id = msg.from_user.id
    user = get_user_by_id(user_id)
    
    if not user:
        username = msg.from_user.username or msg.from_user.first_name or "unknown"
        add_user(user_id, username, role='client')  # is_active=1 по умолчанию
        # Уведомить админа
        try:
            await msg.bot.send_message(
                ADMIN_ID,
                f"👤 Новый пользователь @{username} (id={user_id}) зарегистрировался в боте.")
        except Exception as e:
            print(f"Ошибка уведомления админа: {e}")
        await msg.answer("✅ Вы успешно зарегистрированы! Теперь можете пользоваться ботом.", reply_markup=main_menu_keyboard())
        return
    
    if not user[3]:  # is_active
        await msg.answer("🚫 Ваш аккаунт заблокирован. Обратитесь к администратору.")
        return
    
    await msg.answer("👋 Привет! Управляй кабинетами Авито:", reply_markup=main_menu_keyboard())

async def cancel_cmd(msg: types.Message, state: FSMContext):
    """Обработчик команды /cancel"""
    await state.clear()
    user_id = getattr(getattr(msg, 'from_user', None), 'id', None)
    if user_id is None:
        await msg.answer("Ошибка: не удалось определить пользователя.")
        return
    await msg.answer("❌ Операция отменена.", reply_markup=cabinets_keyboard(user_id))

async def help_cmd(msg: types.Message):
    """Обработчик команды /help"""
    help_text = """
🤖 **Справка по боту:**

**Основные команды:**
• `/start` - Запустить бота
• `/cancel` - Отменить текущую операцию
• `/help` - Показать эту справку

**Функции:**
• ➕ Добавить кабинет Авито
• ✏️ Переименовать кабинет
• 🗑 Удалить кабинет
• 📊 Просмотр статистики баланса

**Как добавить кабинет:**
1. Нажмите "➕ Добавить"
2. Введите **Client ID**
3. Введите **Client Secret**
4. Введите **Advertiser ID**

**Где найти данные:**
• **Client ID** и **Client Secret** - в настройках приложения Авито
• **Advertiser ID** - ID вашего рекламного кабинета

**Примечание:** Все данные сохраняются локально на вашем устройстве.
    """
    await msg.answer(help_text, parse_mode="Markdown")

async def show_main_menu(callback: types.CallbackQuery):
    try:
        # Проверяем, есть ли пользователь в базе
        user_id = callback.from_user.id
        user = get_user_by_id(user_id)
        
        if not user:
            await callback.answer("⛔️ Доступ запрещен. Вы не зарегистрированы в системе.", show_alert=True)
            return
        
        # Проверяем, активен ли пользователь
        if not user[3]:  # is_active
            await callback.answer("🚫 Ваш аккаунт заблокирован. Обратитесь к администратору.", show_alert=True)
            return
        
        is_admin_flag = is_admin(user_id)
        await callback.message.edit_text("👋 Привет! Управляй кабинетами Авито:", reply_markup=main_menu_keyboard(is_admin=is_admin_flag))
    except Exception:
        await callback.message.answer("👋 Привет! Управляй кабинетами Авито:", reply_markup=main_menu_keyboard(is_admin=is_admin_flag)) 

async def request_access_callback(callback: types.CallbackQuery):
    """Обработчик запроса доступа к боту"""
    await callback.answer()
    
    data = callback.data
    if not data or not data.startswith("request_access_"):
        await callback.answer("Ошибка: неверный формат данных.", show_alert=True)
        return
    
    try:
        parts = data.split("_")
        user_id = int(parts[2])
        username = callback.from_user.username or callback.from_user.first_name or "Неизвестный пользователь"
    except (IndexError, ValueError):
        await callback.answer("Ошибка: неверный формат данных.", show_alert=True)
        return
    
    # Отправляем уведомление администратору
    admin_message = (
        f"🔐 **Новый запрос доступа к боту**\n\n"
        f"👤 **Пользователь:** @{username}\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"📅 **Дата:** {callback.message.date.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"Для добавления пользователя используйте админ-панель:\n"
        f"`/admin` → Добавить клиента"
    )
    
    try:
        await callback.bot.send_message(
            ADMIN_ID,
            admin_message,
            parse_mode="Markdown"
        )
        
        # Обновляем сообщение пользователя
        await callback.message.edit_text(
            "✅ Запрос на доступ отправлен администратору!\n\n"
            "Мы уведомим вас, когда доступ будет предоставлен.",
            reply_markup=None
        )
        
    except Exception as e:
        print(f"Ошибка отправки уведомления администратору: {e}")
        await callback.message.edit_text(
            "❌ Ошибка отправки запроса. Попробуйте позже или обратитесь к администратору напрямую.",
            reply_markup=None
        ) 