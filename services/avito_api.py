import aiohttp
import ssl
from typing import Optional, Dict, Any
from config import AVITO_API_BASE_URL, AVITO_BALANCE_ENDPOINT
from database.crud import get_token, save_token
from datetime import datetime

class AvitoAPI:
    """Класс для работы с API Авито"""
    
    def __init__(self):
        self.base_url = AVITO_API_BASE_URL
        # Создаем SSL контекст без проверки сертификата
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
    
    async def get_access_token(self, client_id: str, client_secret: str) -> Optional[str]:
        """Получает access_token через OAuth2 (точно как в рабочем коде)"""
        # 1. Попробовать взять токен из базы
        token = await get_token(client_id, client_secret)
        if token and token.expires_at > datetime.utcnow():
            print(f"🔑 Использую кешированный access_token для client_id: {client_id[:10]}...")
            return token.access_token

        # 2. Если нет — запросить у Avito и сохранить
        try:
            # Очищаем данные от лишних символов
            client_id = client_id.strip()
            client_secret = client_secret.strip()
            
            # Проверяем, что данные не пустые
            if not client_id or not client_secret:
                print(f"❌ Пустые данные: client_id='{client_id}', client_secret='{client_secret}'")
                return None
            
            token_url = "https://api.avito.ru/token/"
            
            # Точные параметры как в рабочем коде
            payload = {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret
            }
            
            print(f"🔑 Запрос токена для client_id: {client_id[:10]}...")
            print(f"🔑 Payload: {payload}")
            
            # Используем SSL контекст без проверки сертификата
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                # POST запрос без дополнительных заголовков, как в рабочем коде
                async with session.post(token_url, data=payload) as response:
                    response_text = await response.text()
                    print(f"🔑 Статус токена: {response.status}")
                    print(f"🔑 Ответ токена: {response_text}")
                    
                    if response.status == 200:
                        try:
                            data = await response.json()
                            access_token = data.get("access_token")
                            expires_in = data.get("expires_in", 3600)
                            if access_token:
                                print(f"✅ Токен получен: {access_token[:20]}...")
                                await save_token(client_id, client_secret, access_token, expires_in)
                                return access_token
                            else:
                                print(f"❌ Токен не найден в ответе: {data}")
                                return None
                        except Exception as json_error:
                            print(f"❌ Ошибка парсинга JSON: {json_error}")
                            print(f"❌ Ответ: {response_text}")
                            return None
                    else:
                        print(f"❌ Ошибка получения токена: {response.status} - {response_text}")
                        return None
        except Exception as e:
            print(f"❌ Ошибка при получении токена: {e}")
            return None
    
    async def get_balance(self, client_id: str, client_secret: str, advertiser_id: str) -> Optional[Dict[str, float]]:
        """Получает баланс кабинета через API Авито (точно как в рабочем коде)"""
        try:
            print(f"💰 Запрос баланса для advertiser_id: {advertiser_id}")
            print(f"💰 Client ID: '{client_id}'")
            print(f"💰 Client Secret: '{client_secret[:10]}...' (длина: {len(client_secret)})")
            
            # 1. Получаем access_token
            access_token = await self.get_access_token(client_id, client_secret)
            if not access_token:
                print("❌ Не удалось получить access_token")
                return None
            
            # 2. Запрос на основной баланс (точно как в рабочем коде)
            balance_url = f"https://api.avito.ru/core/v1/accounts/{advertiser_id}/balance/"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            print(f"💰 Запрос баланса: {balance_url}")
            
            # Используем SSL контекст без проверки сертификата
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(balance_url, headers=headers) as response:
                    response_text = await response.text()
                    print(f"💰 Статус баланса: {response.status}")
                    print(f"💰 Ответ баланса: {response_text}")
                    
                    if response.status == 200:
                        try:
                            balance_data = await response.json()
                            
                            # Проверяем наличие данных о балансе (как в рабочем коде)
                            if "real" in balance_data:
                                real_balance = balance_data["real"]
                                bonus_balance = balance_data.get("bonus", 0)
                                
                                print(f"✅ Баланс (реальный): {real_balance} RUB")
                                if bonus_balance > 0:
                                    print(f"✅ Баланс (бонусный): {bonus_balance} RUB")
                                
                                result = {
                                    "real": real_balance,  # Основной баланс
                                    "bonus": bonus_balance,  # Бонусный баланс
                                    "cpa": None  # CPA баланс будет получен отдельно
                                }
                                
                                # 3. Получаем CPA баланс (как в рабочем коде)
                                cpa_balance = await self.get_cpa_balance(access_token)
                                if cpa_balance is not None:
                                    result["cpa"] = cpa_balance
                                    print(f"✅ CPA Баланс: {cpa_balance} RUB")
                                else:
                                    print("ℹ️ CPA баланс: Другой тариф")
                                
                                return result
                            else:
                                print(f"❌ Ошибка получения баланса: {balance_data}")
                                return None
                        except Exception as json_error:
                            print(f"❌ Ошибка парсинга JSON баланса: {json_error}")
                            print(f"❌ Ответ: {response_text}")
                            return None
                    else:
                        print(f"❌ API Error: {response.status} - {response_text}")
                        return None
        except Exception as e:
            print(f"❌ Ошибка при получении баланса: {e}")
            return None
    
    async def get_cpa_balance(self, access_token: str) -> Optional[float]:
        """Получает CPA баланс (точно как в рабочем коде)"""
        try:
            cpa_balance_url = "https://api.avito.ru/cpa/v3/balanceInfo"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "X-Source": "your_service_name",  # Замените на название вашего сервиса
                "Content-Type": "application/json"
            }
            
            print(f"📊 Запрос CPA баланса: {cpa_balance_url}")
            
            # Используем SSL контекст без проверки сертификата
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                # Используем POST с пустым телом, как в рабочем коде
                async with session.post(cpa_balance_url, headers=headers, json={}) as response:
                    response_text = await response.text()
                    print(f"📊 Статус CPA: {response.status}")
                    print(f"📊 Ответ CPA: {response_text}")
                    
                    if response.status == 200:
                        try:
                            cpa_data = await response.json()
                            if "balance" in cpa_data:
                                # Делим на 100 для сокращения на два знака, как в рабочем коде
                                cpa_balance = cpa_data["balance"] / 100
                                print(f"✅ CPA баланс: {cpa_balance} RUB")
                                return cpa_balance
                            else:
                                print("ℹ️ CPA баланс: Другой тариф")
                                return None
                        except Exception as json_error:
                            print(f"❌ Ошибка парсинга JSON CPA: {json_error}")
                            print(f"❌ Ответ: {response_text}")
                            return None
                    else:
                        print(f"❌ CPA API Error: {response.status} - {response_text}")
                        return None
        except Exception as e:
            print(f"❌ Ошибка при получении CPA баланса: {e}")
            return None
    
    async def get_cabinet_info(self, client_id: str, client_secret: str, advertiser_id: str) -> Optional[Dict[str, Any]]:
        """Получает информацию о кабинете"""
        try:
            access_token = await self.get_access_token(client_id, client_secret)
            if not access_token:
                return None
            
            url = f"{self.base_url}/accounts/{advertiser_id}"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Используем SSL контекст без проверки сертификата
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f"API Error: {response.status} - {await response.text()}")
                        return None
        except Exception as e:
            print(f"Ошибка при получении информации о кабинете: {e}")
            return None
    
    async def get_all_cabinets_balance(self, cabinets: list) -> list:
        """Получает баланс всех кабинетов"""
        balance_data = []
        
        for cabinet in cabinets:
            print(f"\n🔍 Обработка кабинета: {cabinet.name}")
            balance = await self.get_balance(
                cabinet.client_id,
                cabinet.client_secret, 
                cabinet.advertiser_id
            )
            
            if balance:
                status = "✅"
                balance_info = f"Основной: {balance['real']:,.2f} ₽"
                if balance.get("bonus", 0) > 0:
                    balance_info += f"\nБонусный: {balance['bonus']:,.2f} ₽"
                if balance.get("cpa") is not None:
                    balance_info += f"\nCPA: {balance['cpa']:,.2f} ₽"
            else:
                status = "❌"
                balance_info = "Ошибка получения"
            
            balance_data.append({
                "name": cabinet.name,
                "balance": balance,
                "balance_info": balance_info,
                "status": status,
                "client_id": cabinet.client_id,
                "advertiser_id": cabinet.advertiser_id
            })
        
        return balance_data

    async def get_cabinet_balance(self, cabinet) -> dict:
        """Получает баланс конкретного кабинета"""
        try:
            print(f"\n🔍 Получение баланса кабинета: {cabinet.name}")
            balance = await self.get_balance(
                cabinet.client_id,
                cabinet.client_secret, 
                cabinet.advertiser_id
            )
            
            if balance:
                balance_info = f"Основной: {balance['real']:,.2f} ₽"
                if balance.get("bonus", 0) > 0:
                    balance_info += f"\nБонусный: {balance['bonus']:,.2f} ₽"
                if balance.get("cpa") is not None:
                    balance_info += f"\nCPA: {balance['cpa']:,.2f} ₽"
                
                return {
                    "balance": balance,
                    "balance_info": balance_info,
                    "error": None
                }
            else:
                return {
                    "balance": None,
                    "balance_info": None,
                    "error": "Не удалось получить баланс"
                }
        except Exception as e:
            print(f"❌ Ошибка при получении баланса кабинета {cabinet.name}: {e}")
            return {
                "balance": None,
                "balance_info": None,
                "error": str(e)
            }

    async def get_aggregated_stats(self, cabinets: list) -> str:
        """
        Возвращает агрегированную статистику по всем кабинетам в виде обычного текста (без HTML/Markdown).
        """
        if not cabinets:
            return "У вас нет кабинетов для отображения статистики."

        balance_data = await self.get_all_cabinets_balance(cabinets)

        stats_text = "📊 Статистика баланса кабинетов:\n"
        total_real_balance = 0
        total_bonus_balance = 0
        total_cpa_balance = 0
        successful_requests = 0

        for cab_data in balance_data:
            name = cab_data["name"]
            balance = cab_data["balance"]
            if balance is not None:
                total_real_balance += balance.get("real", 0)
                total_bonus_balance += balance.get("bonus", 0)
                if balance.get("cpa") is not None:
                    total_cpa_balance += balance["cpa"]
                successful_requests += 1
                stats_text += f"\n✅ {name}\n"
                if balance.get("real", 0) > 0:
                    stats_text += f"Основной: {balance['real']:,.2f} ₽\n"
                if balance.get("bonus", 0) > 0:
                    stats_text += f"Бонусный: {balance['bonus']:,.2f} ₽\n"
                if balance.get("cpa") is not None:
                    stats_text += f"CPA: {balance['cpa']:,.2f} ₽\n"
            else:
                stats_text += f"\n❌ {name}: Ошибка получения\n"

        stats_text += "\n💰 Общий баланс:\n"
        stats_text += f"• Основной: {total_real_balance:,.2f} ₽\n"
        if total_bonus_balance > 0:
            stats_text += f"• Бонусный: {total_bonus_balance:,.2f} ₽\n"
        if total_cpa_balance > 0:
            stats_text += f"• CPA: {total_cpa_balance:,.2f} ₽\n"
        total_all = total_real_balance + total_bonus_balance + total_cpa_balance
        stats_text += f"• Итого: {total_all:,.2f} ₽\n"

        stats_text += f"\n📈 Успешно получено: {successful_requests}/{len(cabinets)}"

        from datetime import datetime
        current_time = datetime.now().strftime("%H:%M:%S")
        stats_text += f"\nОбновлено: {current_time}"

        return stats_text

# Создаем глобальный экземпляр API
avito_api = AvitoAPI() 