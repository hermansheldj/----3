from typing import Dict, Optional
import logging
from aiogram import types

# Словарь для хранения ID последних сообщений бота для каждого пользователя
# Формат: {user_id: message_id}
bot_messages: Dict[int, int] = {}

async def send_and_cleanup(bot, chat_id: int, text: str, **kwargs) -> Optional[types.Message]:
    """
    Отправляет новое сообщение и удаляет предыдущее сообщение бота для этого пользователя
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        text: Текст сообщения
        **kwargs: Дополнительные параметры для отправки сообщения
    
    Returns:
        Отправленное сообщение или None в случае ошибки
    """
    try:
        # Удаляем предыдущее сообщение бота, если оно существует
        if chat_id in bot_messages:
            try:
                await bot.delete_message(chat_id, bot_messages[chat_id])
                logging.info(f"🗑 Удалено предыдущее сообщение {bot_messages[chat_id]} для пользователя {chat_id}")
            except Exception as e:
                logging.warning(f"Не удалось удалить предыдущее сообщение для пользователя {chat_id}: {e}")
        
        # Отправляем новое сообщение
        message = await bot.send_message(chat_id, text, **kwargs)
        
        # Сохраняем ID нового сообщения
        bot_messages[chat_id] = message.message_id
        logging.info(f"💬 Отправлено новое сообщение {message.message_id} для пользователя {chat_id}")
        
        return message
        
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения пользователю {chat_id}: {e}")
        return None

async def edit_and_cleanup(bot, chat_id: int, message_id: int, text: str, **kwargs) -> bool:
    """
    Редактирует сообщение и удаляет предыдущее сообщение бота для этого пользователя
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        message_id: ID сообщения для редактирования
        text: Новый текст сообщения
        **kwargs: Дополнительные параметры для редактирования
    
    Returns:
        True если успешно, False в случае ошибки
    """
    try:
        # Удаляем предыдущее сообщение бота, если оно существует и отличается от текущего
        if chat_id in bot_messages and bot_messages[chat_id] != message_id:
            try:
                await bot.delete_message(chat_id, bot_messages[chat_id])
                logging.info(f"🗑 Удалено предыдущее сообщение {bot_messages[chat_id]} для пользователя {chat_id}")
            except Exception as e:
                logging.warning(f"Не удалось удалить предыдущее сообщение для пользователя {chat_id}: {e}")
        
        # Редактируем текущее сообщение
        await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            **kwargs
        )
        
        # Сохраняем ID текущего сообщения
        bot_messages[chat_id] = message_id
        logging.info(f"✏️ Отредактировано сообщение {message_id} для пользователя {chat_id}")
        
        return True
        
    except Exception as e:
        logging.error(f"Ошибка при редактировании сообщения для пользователя {chat_id}: {e}")
        return False

def clear_user_messages(user_id: int):
    """
    Очищает историю сообщений для конкретного пользователя
    
    Args:
        user_id: ID пользователя
    """
    if user_id in bot_messages:
        del bot_messages[user_id]
        logging.info(f"🧹 Очищена история сообщений для пользователя {user_id}")

def get_last_message_id(user_id: int) -> Optional[int]:
    """
    Получает ID последнего сообщения бота для пользователя
    
    Args:
        user_id: ID пользователя
    
    Returns:
        ID последнего сообщения или None
    """
    return bot_messages.get(user_id) 