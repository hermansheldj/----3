import asyncio
from aiogram import types
from keyboards.keyboards import cabinets_keyboard, cabinet_detail_keyboard, statistics_menu_keyboard
from services.avito_api import avito_api
from database.crud import get_user_cabinets
from database.message_manager import edit_and_cleanup

async def show_statistics(callback: types.CallbackQuery):
    """Показывает статистику баланса всех кабинетов"""
    user_id = getattr(getattr(callback, 'from_user', None), 'id', None)
    if user_id is None:
        await callback.answer("Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    
    message = getattr(callback, 'message', None)
    if not message:
        await callback.answer("Ошибка: не удалось получить сообщение.", show_alert=True)
        return
    
    # Показываем сообщение о загрузке
    await edit_and_cleanup(
        callback.bot,
        message.chat.id,
        message.message_id,
        "📊 Загружаю статистику..."
    )
    
    # Получаем кабинеты пользователя
    cabinets = await get_user_cabinets(user_id)
    
    if not cabinets:
        await edit_and_cleanup(
            callback.bot,
            message.chat.id,
            message.message_id,
            "📊 У вас нет кабинетов для отображения статистики.",
            reply_markup=cabinets_keyboard(user_id)
        )
        return
    
    # Получаем баланс всех кабинетов
    balance_data = await avito_api.get_all_cabinets_balance(cabinets)
    
    # Формируем текст статистики (без Markdown)
    stats_text = "📊 Статистика баланса кабинетов:\n\n"
    total_real_balance = 0
    total_bonus_balance = 0
    total_cpa_balance = 0
    successful_requests = 0
    
    for cab_data in balance_data:
        name = cab_data["name"]
        balance = cab_data["balance"]
        status = cab_data["status"]
        balance_info = cab_data["balance_info"]
        
        if balance is not None:
            total_real_balance += balance.get("real", 0)
            total_bonus_balance += balance.get("bonus", 0)
            if balance.get("cpa") is not None:
                total_cpa_balance += balance["cpa"]
            successful_requests += 1
            stats_text += f"{status} {name}\n{balance_info}\n\n"
        else:
            stats_text += f"{status} {name}: Ошибка получения\n\n"
    
    if successful_requests > 0:
        stats_text += "💰 Общий баланс:\n"
        stats_text += f"• Основной: {total_real_balance:,.2f} ₽\n"
        if total_bonus_balance > 0:
            stats_text += f"• Бонусный: {total_bonus_balance:,.2f} ₽\n"
        if total_cpa_balance > 0:
            stats_text += f"• CPA: {total_cpa_balance:,.2f} ₽\n"
        total_all = total_real_balance + total_bonus_balance + total_cpa_balance
        stats_text += f"• Итого: {total_all:,.2f} ₽\n\n"
        stats_text += f"📈 Успешно получено: {successful_requests}/{len(cabinets)}"
    
    from datetime import datetime
    current_time = datetime.now().strftime("%H:%M:%S")
    stats_text += f"\n\nОбновлено: {current_time}"
    
    await edit_and_cleanup(
        callback.bot,
        message.chat.id,
        message.message_id,
        stats_text, 
        reply_markup=cabinets_keyboard(user_id)
    )

def get_cab_name(cab):
    if hasattr(cab, 'name'):
        return cab.name
    elif isinstance(cab, dict):
        return cab.get('name', 'Без названия')
    return 'Без названия'

async def show_cabinet_balance(callback: types.CallbackQuery):
    """Показывает баланс конкретного кабинета"""
    data = getattr(callback, 'data', None)
    user_id = getattr(getattr(callback, 'from_user', None), 'id', None)
    if data is None or user_id is None or "_" not in data:
        await callback.answer("Ошибка: не удалось определить кабинет.", show_alert=True)
        return
    
    try:
        cab_id = int(data.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка: неверный формат данных.", show_alert=True)
        return
    
    cabs = await get_user_cabinets(user_id)
    cab = next((c for c in cabs if getattr(c, 'id', None) == cab_id or (isinstance(c, dict) and c.get('id') == cab_id)), None)
    if not cab:
        await callback.answer("Ошибка: кабинет не найден.", show_alert=True)
        return
    
    message = getattr(callback, 'message', None)
    if not message:
        await callback.answer("Ошибка: не удалось получить сообщение.", show_alert=True)
        return
    
    cab_name = get_cab_name(cab)
    # Показываем сообщение о загрузке
    await edit_and_cleanup(
        callback.bot,
        message.chat.id,
        message.message_id,
        f"📊 Загружаю баланс кабинета '{cab_name}'..."
    )
    
    # Получаем баланс кабинета
    balance_data = await avito_api.get_cabinet_balance(cab)
    
    if balance_data["balance"] is not None:
        balance = balance_data["balance"]
        balance_info = balance_data["balance_info"]
        text = f"💰 Баланс кабинета '{cab_name}'\n\n{balance_info}"
        from datetime import datetime
        current_time = datetime.now().strftime("%H:%M:%S")
        text += f"\n\nОбновлено: {current_time}"
        await edit_and_cleanup(
            callback.bot,
            message.chat.id,
            message.message_id,
            text,
            reply_markup=cabinet_detail_keyboard(cab_id)
        )
    else:
        await edit_and_cleanup(
            callback.bot,
            message.chat.id,
            message.message_id,
            f"❌ Ошибка получения баланса кабинета '{cab_name}':\n{balance_data['error']}",
            reply_markup=cabinet_detail_keyboard(cab_id)
        )

async def show_statistics_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cabinets = await get_user_cabinets(user_id)
    # Получить и сформировать агрегированную статистику по всем кабинетам
    stats_text = await avito_api.get_aggregated_stats(cabinets)
    message = getattr(callback, 'message', None)
    if message:
        await message.edit_text(stats_text, reply_markup=statistics_menu_keyboard())
    else:
        await callback.answer("Ошибка: не удалось получить сообщение.", show_alert=True) 