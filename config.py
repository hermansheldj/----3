import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Токен бота (из переменной окружения или по умолчанию)
BOT_TOKEN = os.getenv("BOT_TOKEN", "885100762:AAExXVo5CjhrQDUnU_sJhkFQS7xXMzxr4nE")

# ID администратора (из переменной окружения)
ADMIN_ID = int(os.getenv("ADMIN_ID", "463627119"))

# Файл для хранения данных
STORAGE_FILE = "storage.json"

# Настройки API Авито
AVITO_API_BASE_URL = "https://api.avito.ru/core/v1"
AVITO_BALANCE_ENDPOINT = "/accounts/{advertiser_id}/balance"

# Настройки бота
BOT_COMMANDS = [
    ("start", "Запустить бота"),
    ("cancel", "Отменить текущую операцию"),
    ("help", "Показать справку")
] 