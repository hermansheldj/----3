import asyncio
import logging
import time
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
import sqlite3

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Импорты конфигурации
from config import BOT_TOKEN, ADMIN_ID

# Импорты обработчиков
from handlers.start import start_cmd, cancel_cmd, help_cmd, show_main_menu, request_access_callback
from handlers.cabinets import (
    add_cabinet_step1, add_cabinet_step2, add_cabinet_step3, add_cabinet_step4, add_cabinet_finish,
    select_cabinet, back_to_main, delete_cabinet_start, delete_cabinet_confirm,
    rename_cabinet_start, rename_cabinet_finish, cancel_callback, show_cabinets_menu, add_cabinet_start,
    add_trigger_start, add_trigger_type, add_trigger_threshold, show_triggers, edit_trigger_start, edit_trigger_value,
    show_interval_menu, set_interval
)
from handlers.statistics import show_statistics, show_cabinet_balance, show_statistics_menu
from handlers.admin import (
    admin_menu, admin_list, admin_add, admin_add_username, admin_block, admin_block_username, admin_delete, admin_delete_username, admin_logs, admin_back,
    admin_access_menu, admin_access_user, admin_access_toggle,
    admin_add_cabinet, admin_add_cabinet_finish
)

# Импорты состояний
from states.states import AddCabinet, RenameCabinet, DeleteCabinet, AddTrigger, EditTrigger, AdminPanel, AddUser, BlockUser, DeleteUser, AddCabinetGlobal

from database.crud import (
    get_triggers_for_user, log_trigger_event, save_trigger,
    get_user_cabinets, get_all_users, get_accessible_cabinets
)
from services.avito_api import avito_api

def grant_admin_access_to_all_cabinets():
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    # Получаем все cabinet_id
    c.execute('SELECT id FROM cabinets')
    cabinet_ids = [row[0] for row in c.fetchall()]
    for cab_id in cabinet_ids:
        c.execute('INSERT OR REPLACE INTO permissions (user_id, cabinet_id, has_access) VALUES (?, ?, 1)', (ADMIN_ID, cab_id))
    conn.commit()
    conn.close()

async def trigger_checker(bot):
    while True:
        try:
            all_users = [u[0] for u in get_all_users()]
            for user_id in all_users:
                triggers = get_triggers_for_user(user_id)
                cabs = await get_accessible_cabinets(user_id)
                for trig in triggers:
                    cabinet_id = trig['cabinet_id']
                    # Находим кабинет по cabinet_id
                    cab = next((c for c in cabs if c.id == cabinet_id), None)
                    if not cab:
                        continue
                    name = cab.name
                    trigger_type = trig['trigger_type']
                    threshold = trig['threshold']
                    repeat_interval = trig.get('repeat_interval_minutes', 0) or 0
                    last_alert = trig.get('last_alert_sent_at')
                    # Получаем баланс
                    balance = await avito_api.get_balance(cab.client_id, cab.client_secret, cab.advertiser_id)
                    if not balance:
                        continue
                    if trigger_type == 'real':
                        current = balance.get('real', 0)
                        tname = 'Основной'
                    elif trigger_type == 'cpa':
                        current = balance.get('cpa', 0)
                        tname = 'CPA'
                    elif trigger_type == 'total':
                        current = balance.get('real', 0) + (balance.get('cpa', 0) or 0)
                        tname = 'Общий'
                    else:
                        continue
                    now = int(time.time())
                    if current <= threshold:
                        # Проверка частоты уведомлений
                        should_notify = False
                        if last_alert is None:
                            should_notify = True
                        elif repeat_interval > 0 and now - last_alert >= repeat_interval * 60:
                            should_notify = True
                        # Если repeat_interval == 0 и уже отправляли — не уведомлять повторно
                        if should_notify:
                            text = (
                                "⚠️ *Внимание!*\n"
                                "Бюджет кабинета *{name}* по типу *{tname}*  \n"
                                "опустился ниже установленного порога.\n\n"
                                "📉 *Текущий баланс:* {current:.2f} ₽  \n"
                                "🔻 *Пороговое значение:* {threshold:.2f} ₽"
                            ).format(
                                name=name,
                                tname=tname,
                                current=current,
                                threshold=threshold
                            )
                            print(f"[DEBUG] Кнопка: {text}, callback_data: select_{cab.id}")
                            await bot.send_message(
                                user_id,
                                text,
                                parse_mode='Markdown'
                            )
                            log_trigger_event(user_id, cabinet_id, trigger_type, threshold, current)
                            # Обновляем last_alert_sent_at
                            save_trigger(user_id, cabinet_id, trigger_type, threshold, repeat_interval)
                        # иначе — не уведомлять
                    else:
                        # Баланс выше порога — сбрасываем last_alert_sent_at
                        if last_alert:
                            save_trigger(user_id, cabinet_id, trigger_type, threshold, repeat_interval)
        except Exception as e:
            print(f"[TriggerChecker] Ошибка: {e}")
        await asyncio.sleep(300)  # 5 минут

async def main():
    grant_admin_access_to_all_cabinets()
    """Главная функция бота"""
    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрация обработчиков команд
    dp.message.register(start_cmd, Command("start"))
    dp.message.register(cancel_cmd, Command("cancel"))
    dp.message.register(help_cmd, Command("help"))
    
    # Регистрация обработчиков callback-запросов
    dp.callback_query.register(cancel_callback, F.data == "cancel")
    dp.callback_query.register(add_cabinet_step1, F.data == "add")
    dp.callback_query.register(select_cabinet, F.data.regexp(r"^select_\d+$"))
    dp.callback_query.register(back_to_main, F.data == "back_to_main")
    dp.callback_query.register(delete_cabinet_start, F.data.regexp(r"delete_\d+"))
    dp.callback_query.register(delete_cabinet_confirm, F.data.regexp(r"confirm_delete_\d+"))
    dp.callback_query.register(rename_cabinet_start, F.data.regexp(r"rename_\d+"))
    dp.callback_query.register(show_statistics, F.data == "statistics")
    dp.callback_query.register(show_cabinet_balance, F.data.regexp(r"balance_\d+"))
    dp.callback_query.register(show_main_menu, F.data == "back_to_main")
    dp.callback_query.register(show_cabinets_menu, F.data == "cabinets_menu")
    dp.callback_query.register(show_cabinets_menu, F.data == "cabinets")
    dp.callback_query.register(show_statistics_menu, F.data == "statistics_menu")
    dp.callback_query.register(add_trigger_start, F.data.regexp(r"add_trigger_\d+"))
    dp.callback_query.register(add_trigger_type, F.data.regexp(r"trigger_type_(real|cpa|total)_\d+"))
    dp.callback_query.register(show_triggers, F.data.regexp(r"show_triggers_\d+"))
    dp.callback_query.register(edit_trigger_start, F.data.regexp(r"edit_trigger_\d+_(real|cpa|total)"))
    dp.callback_query.register(show_interval_menu, F.data.regexp(r"set_interval_menu_\d+_(real|cpa|total)"))
    dp.callback_query.register(set_interval, F.data.regexp(r"set_interval_\d+_(real|cpa|total)_\d+"))
    
    # Регистрация обработчиков состояний
    dp.message.register(add_cabinet_step2, AddCabinet.name)
    dp.message.register(add_cabinet_step3, AddCabinet.client_id)
    dp.message.register(add_cabinet_step4, AddCabinet.secret_id)
    dp.message.register(add_cabinet_finish, AddCabinet.advertiser_id)
    dp.message.register(rename_cabinet_finish, RenameCabinet.new_name)
    dp.message.register(add_trigger_threshold, AddTrigger.threshold)
    dp.message.register(edit_trigger_value, EditTrigger.value)
    
    # Регистрация обработчиков админ-панели
    dp.message.register(admin_menu, Command("admin"))
    dp.callback_query.register(admin_list, F.data == "admin_list")
    dp.callback_query.register(admin_add, F.data == "admin_add")
    dp.message.register(admin_add_username, AddUser.username)
    dp.callback_query.register(admin_block, F.data == "admin_block")
    dp.message.register(admin_block_username, BlockUser.username)
    dp.callback_query.register(admin_delete, F.data == "admin_delete")
    dp.message.register(admin_delete_username, DeleteUser.username)
    dp.callback_query.register(admin_logs, F.data == "admin_logs")
    dp.callback_query.register(admin_back, F.data == "admin_back")
    dp.callback_query.register(admin_menu, F.data == "admin_menu")
    dp.callback_query.register(admin_access_menu, F.data == "admin_access")
    dp.callback_query.register(admin_access_user, F.data.regexp(r"^admin_access_user_\d+$"))
    dp.callback_query.register(admin_access_toggle, F.data.regexp(r"^admin_access_toggle_\d+_\d+$"))
    dp.callback_query.register(request_access_callback, F.data.regexp(r"^request_access_\d+$"))
    dp.callback_query.register(admin_add_cabinet, F.data == "admin_add_cabinet")
    dp.message.register(admin_add_cabinet_finish, AddCabinetGlobal.name)
    
    # Запуск бота
    print("🤖 Бот запущен...")
    asyncio.create_task(trigger_checker(bot))
    await dp.start_polling(bot)

# DEBUG universal callback handler for diagnostics
from aiogram import types as _types

def setup_debug_callback(dp):
    @dp.callback_query()
    async def debug_callback(callback: _types.CallbackQuery):
        print(f"[DEBUG CALLBACK] data={callback.data}")
        await callback.answer(f"DEBUG: {callback.data}", show_alert=True)

if __name__ == "__main__":
    import sys
    if "debug" in sys.argv:
        from aiogram import Bot, Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage
        from config import BOT_TOKEN
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher(storage=MemoryStorage())
        setup_debug_callback(dp)
        import asyncio
        asyncio.run(dp.start_polling(bot))
    else:
        asyncio.run(main()) 