from database.crud import get_all_cabinets, get_autoreply_settings
from services.avito_api import get_new_messages, send_avito_reply
from database.crud import get_token
import asyncio

async def auto_reply_job():
    for cab in get_all_cabinets():
        settings = get_autoreply_settings(cab['id'] if isinstance(cab, dict) else cab.id)
        if not settings['enabled']:
            continue
        access_token = await get_token(cab['client_id'] if isinstance(cab, dict) else cab.client_id, cab['client_secret'] if isinstance(cab, dict) else cab.client_secret)
        new_msgs = get_new_messages(access_token, cab['advertiser_id'] if isinstance(cab, dict) else cab.advertiser_id)
        for msg in new_msgs:
            if msg.get('is_incoming') and not msg.get('is_answered'):
                send_avito_reply(access_token, cab['advertiser_id'] if isinstance(cab, dict) else cab.advertiser_id, msg['dialog_id'], settings['text'])

async def start_auto_reply_scheduler():
    while True:
        await auto_reply_job()
        await asyncio.sleep(60) 