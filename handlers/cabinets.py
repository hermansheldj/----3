from aiogram import types, F
from aiogram.fsm.context import FSMContext
from states.states import AddCabinet, RenameCabinet, DeleteCabinet, AddTrigger, EditTrigger
from keyboards.keyboards import cabinets_keyboard, cancel_keyboard, cabinet_detail_keyboard, confirm_keyboard, cabinets_menu_keyboard, main_menu_keyboard, trigger_type_keyboard, trigger_list_keyboard, notification_interval_keyboard
from database.message_manager import send_and_cleanup, edit_and_cleanup
from database.crud import save_trigger, get_triggers_for_user, add_cabinet, get_user_cabinets, get_accessible_cabinets, get_all_users, remove_cabinet_by_index, update_cabinet_name_by_index, remove_cabinet_by_id, set_autoreply_settings, get_autoreply_settings, delete_trigger
import logging
import aiogram
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.permissions import is_admin
from aiogram.fsm.state import State, StatesGroup

async def add_cabinet_step1(callback: types.CallbackQuery, state: FSMContext):
    """Начало добавления кабинета - запрос названия"""
    await callback.answer()
    message = getattr(callback, 'message', None)
    if not message:
        await callback.answer("Ошибка: не удалось получить сообщение.", show_alert=True)
        return
    await edit_and_cleanup(
        callback.bot,
        message.chat.id,
        message.message_id,
        "Введи название кабинета:\n\nИли нажми ❌ Отмена для выхода",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(AddCabinet.name)

async def add_cabinet_step2(msg: types.Message, state: FSMContext):
    """Второй шаг добавления - сохранение названия и запрос client_id"""
    text = getattr(msg, 'text', None)
    if text is None:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: не удалось получить название кабинета.")
        return
    
    # Очищаем от лишних пробелов и символов
    name = text.strip()
    if not name:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: название кабинета не может быть пустым.")
        return
    
    await state.update_data(name=name)
    await send_and_cleanup(
        msg.bot, 
        msg.chat.id, 
        "Введи Client ID:\n\nИли нажми ❌ Отмена для выхода", 
        reply_markup=cancel_keyboard()
    )
    await state.set_state(AddCabinet.client_id)

async def add_cabinet_step3(msg: types.Message, state: FSMContext):
    """Третий шаг добавления - сохранение client_id и запрос client_secret"""
    text = getattr(msg, 'text', None)
    if text is None:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: не удалось получить Client ID.")
        return
    
    # Очищаем от лишних пробелов и символов
    client_id = text.strip()
    if not client_id:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: Client ID не может быть пустым.")
        return
    
    await state.update_data(client_id=client_id)
    await send_and_cleanup(
        msg.bot, 
        msg.chat.id, 
        "Введи Client Secret:\n\nИли нажми ❌ Отмена для выхода", 
        reply_markup=cancel_keyboard()
    )
    await state.set_state(AddCabinet.secret_id)

async def add_cabinet_step4(msg: types.Message, state: FSMContext):
    """Четвертый шаг добавления - сохранение client_secret и запрос advertiser_id"""
    text = getattr(msg, 'text', None)
    if text is None:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: не удалось получить Client Secret.")
        return
    
    # Очищаем от лишних пробелов и символов
    client_secret = text.strip()
    if not client_secret:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: Client Secret не может быть пустым.")
        return
    
    await state.update_data(secret_id=client_secret)
    await send_and_cleanup(
        msg.bot, 
        msg.chat.id, 
        "Введи Advertiser ID:\n\nИли нажми ❌ Отмена для выхода", 
        reply_markup=cancel_keyboard()
    )
    await state.set_state(AddCabinet.advertiser_id)

async def add_cabinet_finish(msg: types.Message, state: FSMContext):
    """Завершение добавления кабинета"""
    data = await state.get_data()
    user_id = getattr(getattr(msg, 'from_user', None), 'id', None)
    text = getattr(msg, 'text', None)
    if user_id is None or text is None:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: не удалось получить данные пользователя или Advertiser ID.")
        return
    advertiser_id = text.strip()
    if not advertiser_id:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: Advertiser ID не может быть пустым.")
        return
    try:
        int(advertiser_id)
    except ValueError:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: Advertiser ID должен быть числом.")
        return
    await add_cabinet(user_id, data["name"], data["client_id"], data["secret_id"], advertiser_id)
    await state.clear()
    cabs = await get_accessible_cabinets(user_id)
    await send_and_cleanup(
        msg.bot,
        msg.chat.id,
        f"✅ Кабинет '{data['name']}' добавлен!",
        reply_markup=await cabinets_keyboard(user_id, active_idx=len(cabs)-1)
    )

async def select_cabinet(callback: types.CallbackQuery):
    await callback.answer()
    logging.info("select_cabinet called")
    data = getattr(callback, 'data', None)
    user_id = getattr(getattr(callback, 'from_user', None), 'id', None)
    logging.info(f"select_cabinet: data={data}, user_id={user_id}")
    if data is None or user_id is None or "_" not in data:
        await callback.answer("Ошибка: не удалось определить кабинет.", show_alert=True)
        logging.error("select_cabinet: invalid data or user_id")
        return
    try:
        cab_id = int(data.split("_")[1])
        logging.info(f"select_cabinet: cab_id={cab_id}")
    except (IndexError, ValueError) as e:
        await callback.answer("Ошибка: неверный формат данных.", show_alert=True)
        logging.error(f"select_cabinet: exception in cab_id parsing: {e}")
        return
    try:
        if is_admin(user_id):
            cabs = await get_user_cabinets(user_id)
        else:
            cabs = await get_accessible_cabinets(user_id)
        logging.info(f"select_cabinet: cabs count={len(cabs)}")
        cab = next((c for c in cabs if c.id == cab_id), None)
        if not cab:
            await callback.answer("Ошибка: кабинет не найден.", show_alert=True)
            logging.error(f"select_cabinet: cab_id {cab_id} not found")
            return
        text = (f"🔹 {cab.name}\n"
                f"Client ID: {cab.client_id}\n"
                f"Client Secret: {cab.client_secret}\n"
                f"Advertiser ID: {cab.advertiser_id}")
        message = getattr(callback, 'message', None)
        if not message:
            await callback.answer("Ошибка: не удалось получить сообщение.", show_alert=True)
            logging.error("select_cabinet: message is None")
            return
        logging.info(f"select_cabinet: sending edit_and_cleanup for chat_id={message.chat.id}, message_id={message.message_id}")
        await edit_and_cleanup(
            callback.bot,
            message.chat.id,
            message.message_id,
            text,
            reply_markup=cabinet_detail_keyboard(cab_id)
        )
        logging.info("select_cabinet: edit_and_cleanup sent successfully")
    except Exception as e:
        logging.error(f"select_cabinet: unexpected exception: {e}", exc_info=True)
        await callback.answer("Произошла внутренняя ошибка при открытии кабинета.", show_alert=True)

async def delete_cabinet_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало удаления кабинета"""
    await callback.answer()
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
    cabs = await get_accessible_cabinets(user_id)
    cab = next((c for c in cabs if c.id == cab_id), None)
    if not cab:
        await callback.answer("Ошибка: кабинет не найден.", show_alert=True)
        return
    await state.update_data(cabinet_id=cab_id)
    message = getattr(callback, 'message', None)
    if not message:
        await callback.answer("Ошибка: не удалось получить сообщение.", show_alert=True)
        return
    await edit_and_cleanup(
        callback.bot,
        message.chat.id,
        message.message_id,
        f"🗑 Удалить кабинет '{cab.name}'?\n\nЭто действие нельзя отменить.",
        reply_markup=confirm_keyboard("delete", str(cab_id))
    )

async def delete_cabinet_confirm(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение удаления кабинета"""
    await callback.answer()
    data = getattr(callback, 'data', None)
    user_id = getattr(getattr(callback, 'from_user', None), 'id', None)
    if data is None or user_id is None or "_" not in data:
        await callback.answer("Ошибка: не удалось определить действие.", show_alert=True)
        return
    try:
        cab_id = int(data.split("_")[-1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка: неверный формат данных.", show_alert=True)
        return
    cabs = await get_accessible_cabinets(user_id)
    cab = next((c for c in cabs if c.id == cab_id), None)
    if not cab:
        await callback.answer("Ошибка: кабинет не найден.", show_alert=True)
        return
    cab_name = cab.name
    # Удаляем кабинет по id
    remove_cabinet_by_id(cab_id)
    message = getattr(callback, 'message', None)
    if not message:
        await callback.answer("Ошибка: не удалось получить сообщение.", show_alert=True)
        return
    await edit_and_cleanup(
        callback.bot,
        message.chat.id,
        message.message_id,
        f"🗑 Кабинет '{cab_name}' удален.",
        reply_markup=await cabinets_keyboard(user_id)
    )

async def rename_cabinet_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало переименования кабинета"""
    await callback.answer()
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
    cabs = await get_accessible_cabinets(user_id)
    cab = next((c for c in cabs if c.id == cab_id), None)
    if not cab:
        await callback.answer("Ошибка: кабинет не найден.", show_alert=True)
        return
    await state.update_data(cabinet_id=cab_id)
    message = getattr(callback, 'message', None)
    if not message:
        await callback.answer("Ошибка: не удалось получить сообщение.", show_alert=True)
        return
    await edit_and_cleanup(
        callback.bot,
        message.chat.id,
        message.message_id,
        f"Введи новое имя для кабинета '{cab.name}':\n\nИли нажми ❌ Отмена для выхода",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(RenameCabinet.new_name)

async def rename_cabinet_finish(msg: types.Message, state: FSMContext):
    """Завершение переименования кабинета"""
    user_id = getattr(getattr(msg, 'from_user', None), 'id', None)
    text = getattr(msg, 'text', None)
    if user_id is None or text is None:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: не удалось получить данные пользователя или имя.")
        await state.clear()
        return
    new_name = text.strip()
    if not new_name:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: название кабинета не может быть пустым.")
        return
    data = await state.get_data()
    cabinet_id = data.get('cabinet_id')
    cabs = await get_accessible_cabinets(user_id)
    cab = next((c for c in cabs if c.id == cabinet_id), None)
    if not cab:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: кабинет не найден.")
        await state.clear()
        return
    old_name = cab.name
    # ok = update_cabinet_name_by_index(user_id, cabinet_index, new_name)
    await send_and_cleanup(
        msg.bot,
        msg.chat.id,
        f"✏️ Кабинет переименован: '{old_name}' → '{new_name}'",
        reply_markup=await cabinets_keyboard(user_id, active_idx=cabinet_id)
    )
    await state.clear()

async def cancel_callback(callback: types.CallbackQuery, state: FSMContext):
    """Отмена текущего действия"""
    await callback.answer()
    user_id = getattr(getattr(callback, 'from_user', None), 'id', None)
    if user_id is None:
        await callback.answer("Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    
    message = getattr(callback, 'message', None)
    if not message:
        await callback.answer("Ошибка: не удалось получить сообщение.", show_alert=True)
        return
    
    await state.clear()
    await edit_and_cleanup(
        callback.bot,
        message.chat.id,
        message.message_id,
        "🏢 Управление кабинетами\n\nВыбери действие:",
        reply_markup=await cabinets_keyboard(user_id)
    )

async def show_cabinets_menu(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    message = getattr(callback, 'message', None)
    if message and hasattr(message, 'edit_text'):
        try:
            await message.edit_text("🏢 Ваши кабинеты:", reply_markup=await cabinets_keyboard(user_id))
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                pass
            else:
                raise
    else:
        await callback.answer("Ошибка: не удалось получить сообщение.", show_alert=True)

async def back_to_main(callback: types.CallbackQuery):
    await callback.answer()
    message = getattr(callback, 'message', None)
    if message and hasattr(message, 'edit_text'):
        try:
            await message.edit_text("👋 Привет! Управляй кабинетами Авито:", reply_markup=main_menu_keyboard())
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                pass
            else:
                try:
                    await message.answer("👋 Привет! Управляй кабинетами Авито:", reply_markup=main_menu_keyboard())
                except Exception:
                    pass
        except Exception:
            try:
                await message.answer("👋 Привет! Управляй кабинетами Авито:", reply_markup=main_menu_keyboard())
            except Exception:
                pass
    else:
        await callback.answer("Ошибка: не удалось получить сообщение.", show_alert=True)

async def add_cabinet_start(callback: types.CallbackQuery, state):
    await callback.answer()
    message = getattr(callback, 'message', None)
    if message and hasattr(message, 'edit_text'):
        try:
            await message.edit_text("Введите client_id:")
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                pass
            else:
                raise
    else:
        await callback.answer("Ошибка: не удалось получить сообщение.", show_alert=True)

# 1. Обработчик кнопки 'Добавить триггер'
async def add_trigger_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = getattr(callback, 'data', None)
    user_id = getattr(getattr(callback, 'from_user', None), 'id', None)
    if data is None or user_id is None or "_" not in data:
        await callback.answer("Ошибка: не удалось определить кабинет.", show_alert=True)
        return
    try:
        cab_id = int(data.split("_")[-1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка: неверный формат данных.", show_alert=True)
        return
    await state.update_data(cabinet_id=cab_id)
    await state.set_state(AddTrigger.type)
    message = getattr(callback, 'message', None)
    if message and hasattr(message, 'edit_text'):
        try:
            await message.edit_text(
                "Выберите тип бюджета для триггера:",
                reply_markup=trigger_type_keyboard(cab_id)
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                pass
            else:
                raise
    else:
        await callback.answer("Ошибка: не удалось получить сообщение.", show_alert=True)

# 2. Обработчик выбора типа бюджета
async def add_trigger_type(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = getattr(callback, 'data', None)
    user_id = getattr(getattr(callback, 'from_user', None), 'id', None)
    if data is None or user_id is None:
        await callback.answer("Ошибка: не удалось определить тип.", show_alert=True)
        return
    try:
        parts = data.split("_")
        trigger_type = parts[2]  # real/cpa/total
        cab_id = int(parts[3])
    except Exception:
        await callback.answer("Ошибка: неверный формат данных.", show_alert=True)
        return
    await state.update_data(trigger_type=trigger_type)
    await state.set_state(AddTrigger.threshold)
    message = getattr(callback, 'message', None)
    if message and hasattr(message, 'edit_text'):
        try:
            await message.edit_text(
                f"Введите пороговое значение для типа '{'Основной' if trigger_type=='real' else ('CPA' if trigger_type=='cpa' else 'Общий')}' (в рублях):"
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                pass
            else:
                raise
    else:
        await callback.answer("Ошибка: не удалось получить сообщение.", show_alert=True)

# 3. Обработчик ввода порога
async def add_trigger_threshold(msg: types.Message, state: FSMContext):
    user_id = getattr(getattr(msg, 'from_user', None), 'id', None)
    text = getattr(msg, 'text', None)
    if user_id is None or text is None:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: не удалось получить данные пользователя или порог.")
        await state.clear()
        return
    try:
        threshold = float(text.replace(",", "."))
        if threshold <= 0:
            raise ValueError
    except Exception:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: введите положительное число.")
        return
    data = await state.get_data()
    cabinet_id = data.get('cabinet_id')
    trigger_type = data.get('trigger_type')
    if cabinet_id is None or trigger_type is None:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: не удалось определить кабинет или тип.")
        await state.clear()
        return
    save_trigger(user_id, cabinet_id, trigger_type, threshold)
    # После добавления триггера возвращаем пользователя к деталям кабинета
    cabs = await get_accessible_cabinets(user_id)
    cab = next((c for c in cabs if c.id == cabinet_id), None)
    if not cab:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: кабинет не найден.")
        await state.clear()
        return
    text = (f"🔹 {cab.name}\n"
            f"Client ID: {cab.client_id}\n"
            f"Client Secret: {cab.client_secret}\n"
            f"Advertiser ID: {cab.advertiser_id}")
    await send_and_cleanup(
        msg.bot,
        msg.chat.id,
        f"✅ Триггер установлен!\nТип: {'Основной' if trigger_type=='real' else ('CPA' if trigger_type=='cpa' else 'Общий')}\nПорог: {threshold:.2f} ₽\n\n" + text,
        reply_markup=cabinet_detail_keyboard(cabinet_id)
    )
    await state.clear()

async def show_triggers(callback: types.CallbackQuery):
    await callback.answer()
    logging.info("show_triggers called")
    data = getattr(callback, 'data', None)
    user_id = getattr(getattr(callback, 'from_user', None), 'id', None)
    logging.info(f"show_triggers: data={data}, user_id={user_id}")
    if data is None or user_id is None or "_" not in data:
        await callback.answer("Ошибка: не удалось определить кабинет.", show_alert=True)
        logging.error("show_triggers: invalid data or user_id")
        return
    try:
        cab_id = int(data.split("_")[-1])
        logging.info(f"show_triggers: cab_id={cab_id}")
    except (IndexError, ValueError) as e:
        await callback.answer("Ошибка: неверный формат данных.", show_alert=True)
        logging.error(f"show_triggers: exception in cab_id parsing: {e}")
        return
    # Получаем триггеры пользователя для этого кабинета
    all_triggers = get_triggers_for_user(user_id)
    logging.info(f"show_triggers: all triggers for user: {all_triggers}")
    triggers = [t for t in all_triggers if t['cabinet_id'] == cab_id]
    logging.info(f"show_triggers: found {len(triggers)} triggers for cabinet {cab_id}: {triggers}")
    if not triggers:
        text = "🔔 У вас нет триггеров для этого кабинета."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить триггер", callback_data=f"add_trigger_{cab_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"cabinet_{cab_id}")]
        ])
    else:
        text = "🔔 Ваши триггеры:\n"
        for t in triggers:
            tname = {'real': 'Основной', 'cpa': 'CPA', 'total': 'Общий'}.get(t['trigger_type'], t['trigger_type'])
            text += f"• {tname}: {t['threshold']:.2f} ₽\n"
        kb = trigger_list_keyboard(cab_id, triggers)
    logging.info(f"show_triggers: generated text: {text}")
    message = getattr(callback, 'message', None)
    if message is not None and hasattr(message, 'edit_text'):
        try:
            logging.info(f"show_triggers: sending edit_text for chat_id={message.chat.id}, message_id={message.message_id}")
            await message.edit_text(text, reply_markup=kb)
            logging.info("show_triggers: edit_text sent successfully")
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                logging.info("show_triggers: message is not modified, ignoring")
                pass
            else:
                logging.error(f"show_triggers: TelegramBadRequest: {e}")
                raise
        except Exception as e:
            logging.error(f"show_triggers: unexpected exception: {e}", exc_info=True)
            raise
    else:
        logging.error("show_triggers: message is None or doesn't have edit_text")
        await callback.answer("Ошибка: не удалось получить сообщение.", show_alert=True)

# Новый обработчик для кнопки "Изменить триггер"
async def edit_trigger_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = getattr(callback, 'data', None)
    user_id = getattr(getattr(callback, 'from_user', None), 'id', None)
    if not data or user_id is None:
        await callback.answer("Ошибка: не удалось определить триггер.", show_alert=True)
        return
    try:
        parts = data.split('_')
        cab_id = int(parts[2])
        trigger_type = parts[3]
    except Exception:
        await callback.answer("Ошибка: неверный формат данных.", show_alert=True)
        return
    await state.update_data(cabinet_id=cab_id, trigger_type=trigger_type)
    await state.set_state(EditTrigger.value)
    if callback.message is not None and hasattr(callback.message, 'edit_text'):
        await callback.message.edit_text(f"Введите новое пороговое значение для триггера '{'Основной' if trigger_type=='real' else ('CPA' if trigger_type=='cpa' else 'Общий')}' (в рублях):\n\n❌ Для отмены нажмите /cancel", reply_markup=cancel_keyboard())

# FSM: обработка ввода нового значения
async def edit_trigger_value(msg: types.Message, state: FSMContext):
    user_id = getattr(getattr(msg, 'from_user', None), 'id', None)
    text = getattr(msg, 'text', None)
    if user_id is None or text is None:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: не удалось получить данные пользователя или значение.")
        await state.clear()
        return
    try:
        value = float(text.replace(",", "."))
        if value <= 0:
            raise ValueError
    except Exception:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: введите положительное число.")
        return
    data = await state.get_data()
    cabinet_id = data.get('cabinet_id')
    trigger_type = data.get('trigger_type')
    if cabinet_id is None or trigger_type is None:
        await send_and_cleanup(msg.bot, msg.chat.id, "Ошибка: не удалось определить триггер.")
        await state.clear()
        return
    save_trigger(user_id, cabinet_id, trigger_type, value)
    await state.clear()
    # Показываем обновлённый список триггеров
    triggers = [t for t in get_triggers_for_user(user_id) if t['cabinet_id'] == cabinet_id]
    if not triggers:
        text = "🔔 У вас нет триггеров для этого кабинета."
        kb = cabinet_detail_keyboard(cabinet_id)
    else:
        text = "🔔 Ваши триггеры:\n"
        for t in triggers:
            tname = {'real': 'Основной', 'cpa': 'CPA', 'total': 'Общий'}.get(t['trigger_type'], t['trigger_type'])
            text += f"• {tname}: {t['threshold']:.2f} ₽\n"
        kb = trigger_list_keyboard(cabinet_id, triggers)
    await send_and_cleanup(msg.bot, msg.chat.id, text, reply_markup=kb)

# Обработчик меню выбора интервала
async def show_interval_menu(callback: types.CallbackQuery):
    await callback.answer()
    data = getattr(callback, 'data', None)
    user_id = getattr(getattr(callback, 'from_user', None), 'id', None)
    if not data or user_id is None:
        await callback.answer("Ошибка: не удалось определить триггер.", show_alert=True)
        return
    try:
        parts = data.split('_')
        cab_id = int(parts[3])
        trigger_type = parts[4]
    except Exception:
        await callback.answer("Ошибка: неверный формат данных.", show_alert=True)
        return
    triggers = [t for t in get_triggers_for_user(user_id) if t['cabinet_id'] == cab_id and t['trigger_type'] == trigger_type]
    if not triggers:
        await callback.answer("Триггер не найден.", show_alert=True)
        return
    current_value = triggers[0].get('repeat_interval_minutes', 0)
    if callback.message is not None and hasattr(callback.message, 'edit_text'):
        await callback.message.edit_text(
            f"Выберите частоту повторных уведомлений для триггера '{'Основной' if trigger_type=='real' else ('CPA' if trigger_type=='cpa' else 'Общий')}'",
            reply_markup=notification_interval_keyboard(trigger_type, cab_id, current_value)
        )

async def set_interval(callback: types.CallbackQuery):
    await callback.answer()
    data = callback.data
    parts = data.split('_')
    cab_id = int(parts[2])
    trigger_type = parts[3]
    val = int(parts[4])
    triggers = [t for t in get_triggers_for_user(callback.from_user.id) if t['cabinet_id'] == cab_id and t['trigger_type'] == trigger_type]
    if not triggers:
        await callback.answer("Триггер не найден.", show_alert=True)
        return
    threshold = triggers[0]['threshold']
    save_trigger(callback.from_user.id, cab_id, trigger_type, threshold, repeat_interval_minutes=val)
    await callback.message.edit_text(
        f"Интервал уведомлений установлен: {'Не напоминать повторно' if val == 0 else f'{val // 60} ч.'}",
        reply_markup=trigger_list_keyboard(cab_id, get_triggers_for_user(callback.from_user.id))
    )

def is_admin(user_id):
    users = get_all_users()
    for u in users:
        if u[0] == user_id and u[2] == 'admin' and u[3] == 1:
            return True
    return False

class AutoReplyState(StatesGroup):
    text = State()

# Клавиатура для управления автоответом
def autoreply_keyboard(cab_id, enabled):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Автоответ включён" if enabled else "❌ Автоответ выключен",
            callback_data=f"toggle_autoreply_{cab_id}"
        )],
        [InlineKeyboardButton(text="✏️ Изменить текст автоответа", callback_data=f"edit_autoreply_text_{cab_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"cabinet_{cab_id}")]
    ])

# Обработчик кнопки управления автоответом
async def show_autoreply_settings(callback: types.CallbackQuery):
    await callback.answer()
    data = callback.data
    cab_id = int(data.split('_')[-1])
    settings = get_autoreply_settings(cab_id)
    await callback.message.edit_text(
        f"⚙️ Настройки автоответа:\n\nСтатус: {'Включён' if settings['enabled'] else 'Выключен'}\nТекст: {settings['text'] or '—'}",
        reply_markup=autoreply_keyboard(cab_id, settings['enabled'])
    )

# Включить/выключить автоответ
async def toggle_autoreply(callback: types.CallbackQuery):
    await callback.answer()
    data = callback.data
    cab_id = int(data.split('_')[-1])
    settings = get_autoreply_settings(cab_id)
    set_autoreply_settings(cab_id, not settings['enabled'], settings['text'])
    await show_autoreply_settings(callback)

# Изменить текст автоответа
async def edit_autoreply_text(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    cab_id = int(callback.data.split('_')[-1])
    await state.update_data(cab_id=cab_id)
    await callback.message.edit_text("Введи новый текст автоответа:")
    await state.set_state(AutoReplyState.text)

async def save_autoreply_text(msg: types.Message, state: FSMContext):
    text = msg.text.strip()
    data = await state.get_data()
    cab_id = data.get('cab_id')
    settings = get_autoreply_settings(cab_id)
    set_autoreply_settings(cab_id, settings['enabled'], text)
    await msg.answer(f"Текст автоответа обновлён!", reply_markup=autoreply_keyboard(cab_id, settings['enabled']))
    await state.clear()

async def delete_trigger_callback(callback: types.CallbackQuery):
    await callback.answer()
    data = callback.data
    user_id = getattr(getattr(callback, 'from_user', None), 'id', None)
    if not data or user_id is None:
        await callback.answer("Ошибка: не удалось определить триггер.", show_alert=True)
        return
    try:
        parts = data.split('_')
        cab_id = int(parts[2])
        trigger_type = parts[3]
    except Exception:
        await callback.answer("Ошибка: неверный формат данных.", show_alert=True)
        return
    delete_trigger(user_id, cab_id, trigger_type)
    # Показываем обновлённый список триггеров
    all_triggers = get_triggers_for_user(user_id)
    triggers = [t for t in all_triggers if t['cabinet_id'] == cab_id]
    if not triggers:
        text = "🔔 У вас нет триггеров для этого кабинета."
        kb = cabinet_detail_keyboard(cab_id)
    else:
        text = "🔔 Ваши триггеры:\n"
        for t in triggers:
            tname = {'real': 'Основной', 'cpa': 'CPA', 'total': 'Общий'}.get(t['trigger_type'], t['trigger_type'])
            text += f"• {tname}: {t['threshold']:.2f} ₽\n"
        kb = trigger_list_keyboard(cab_id, triggers)
    await callback.message.edit_text(text, reply_markup=kb) 