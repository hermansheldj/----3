from database.models import Cabinet, async_session, AvitoToken, Permission
from sqlalchemy import select
from datetime import datetime, timedelta
import sqlite3
from typing import Optional, List, Dict, Any
import time
import logging
from config import ADMIN_ID

async def add_cabinet(user_id, name, client_id, client_secret, advertiser_id):
    async with async_session() as session:
        cabinet = Cabinet(
            user_id=user_id,
            name=name,
            client_id=client_id,
            client_secret=client_secret,
            advertiser_id=advertiser_id
        )
        session.add(cabinet)
        await session.commit()

async def get_user_cabinets(user_id):
    async with async_session() as session:
        # Получаем свои кабинеты
        own_cabs_result = await session.execute(
            select(Cabinet).where(Cabinet.user_id == user_id)
        )
        own_cabs = own_cabs_result.scalars().all()
        # Получаем доступные по permissions
        perm_cabs_result = await session.execute(
            select(Cabinet).join(Permission, Cabinet.id == Permission.cabinet_id).where(
                Permission.user_id == user_id,
                Permission.has_access == 1
            )
        )
        perm_cabs = perm_cabs_result.scalars().all()
        # Собираем уникальные кабинеты (по id)
        all_cabs = {c.id: c for c in perm_cabs}
        for c in own_cabs:
            all_cabs[c.id] = c
        return list(all_cabs.values())

async def get_token(client_id, client_secret):
    async with async_session() as session:
        result = await session.execute(
            select(AvitoToken).where(
                AvitoToken.client_id == client_id,
                AvitoToken.client_secret == client_secret
            )
        )
        return result.scalar_one_or_none()

async def save_token(client_id, client_secret, access_token, expires_in):
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    async with async_session() as session:
        token = await get_token(client_id, client_secret)
        if token:
            token.access_token = access_token
            token.expires_at = expires_at
        else:
            token = AvitoToken(
                client_id=client_id,
                client_secret=client_secret,
                access_token=access_token,
                expires_at=expires_at
            )
            session.add(token)
        await session.commit()

# --- Триггеры бюджета ---

def ensure_trigger_columns():
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    # Проверяем наличие новых столбцов, если нет — добавляем
    try:
        c.execute('SELECT last_alert_sent_at, repeat_interval_minutes FROM triggers LIMIT 1')
    except sqlite3.OperationalError:
        try:
            c.execute('ALTER TABLE triggers ADD COLUMN last_alert_sent_at INTEGER')
        except Exception:
            pass
        try:
            c.execute('ALTER TABLE triggers ADD COLUMN repeat_interval_minutes INTEGER DEFAULT 0')
        except Exception:
            pass
    conn.commit()
    conn.close()

# Вызывать при старте
ensure_trigger_columns()

def save_trigger(user_id: int, cabinet_id: int, trigger_type: str, threshold: float, repeat_interval_minutes: int = 0):
    ensure_trigger_columns()
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS triggers (
            user_id INTEGER,
            cabinet_id INTEGER,
            trigger_type TEXT,
            threshold REAL,
            last_alert_sent_at INTEGER,
            repeat_interval_minutes INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, cabinet_id, trigger_type)
        )
    ''')
    c.execute('''
        INSERT INTO triggers (user_id, cabinet_id, trigger_type, threshold, repeat_interval_minutes)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, cabinet_id, trigger_type) DO UPDATE SET threshold=excluded.threshold, repeat_interval_minutes=excluded.repeat_interval_minutes
    ''', (user_id, cabinet_id, trigger_type, threshold, repeat_interval_minutes))
    conn.commit()
    conn.close()

def get_triggers_for_user(user_id: int):
    ensure_trigger_columns()
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('''
        SELECT cabinet_id, trigger_type, threshold, last_alert_sent_at, repeat_interval_minutes FROM triggers WHERE user_id = ?
    ''', (user_id,))
    rows = c.fetchall()
    conn.close()
    return [
        {
            "cabinet_id": row[0],
            "trigger_type": row[1],
            "threshold": row[2],
            "last_alert_sent_at": row[3],
            "repeat_interval_minutes": row[4]
        }
        for row in rows
    ]

def get_trigger(user_id: int, cabinet_id: int, trigger_type: str) -> Optional[float]:
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('''
        SELECT threshold FROM triggers WHERE user_id = ? AND cabinet_id = ? AND trigger_type = ?
    ''', (user_id, cabinet_id, trigger_type))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

def log_trigger_event(user_id: int, cabinet_id: int, trigger_type: str, threshold: float, current_value: float):
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS trigger_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            cabinet_id INTEGER,
            trigger_type TEXT,
            threshold REAL,
            current_value REAL,
            event_time INTEGER
        )
    ''')
    c.execute('''
        INSERT INTO trigger_events (user_id, cabinet_id, trigger_type, threshold, current_value, event_time)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, cabinet_id, trigger_type, threshold, current_value, int(time.time())))
    conn.commit()
    conn.close()

def get_trigger_events(user_id: int, cabinet_id: int, trigger_type: str, limit: int = 10):
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('''
        SELECT threshold, current_value, event_time FROM trigger_events
        WHERE user_id = ? AND cabinet_id = ? AND trigger_type = ?
        ORDER BY event_time DESC LIMIT ?
    ''', (user_id, cabinet_id, trigger_type, limit))
    rows = c.fetchall()
    conn.close()
    return rows

def ensure_admin_tables():
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            role TEXT,
            is_active INTEGER DEFAULT 1,
            created_at INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT,
            target_user_id INTEGER,
            target_username TEXT,
            timestamp INTEGER
        )
    ''')
    conn.commit()
    conn.close()

ensure_admin_tables()

def add_user(user_id: int, username: str, role: str = 'client'):
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO users (user_id, username, role, is_active, created_at)
        VALUES (?, ?, ?, 1, strftime('%s','now'))
    ''', (user_id, username, role))
    conn.commit()
    conn.close()

def find_user_by_username(username: str):
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('SELECT user_id, username, role, is_active FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    return row

def set_user_active(user_id: int, active: int):
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('UPDATE users SET is_active = ? WHERE user_id = ?', (active, user_id))
    conn.commit()
    conn.close()

def delete_user(user_id: int):
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def log_admin_action(admin_id: int, action: str, target_user_id: int, target_username: str):
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('''
        INSERT INTO admin_logs (admin_id, action, target_user_id, target_username, timestamp)
        VALUES (?, ?, ?, ?, strftime('%s','now'))
    ''', (admin_id, action, target_user_id, target_username))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('SELECT user_id, username, role, is_active, created_at FROM users')
    rows = c.fetchall()
    conn.close()
    return rows

def get_admin_logs(limit=50):
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('SELECT admin_id, action, target_user_id, target_username, timestamp FROM admin_logs ORDER BY timestamp DESC LIMIT ?', (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def init_super_admin():
    # Удалить старого супер-админа, если был
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE user_id = ?', (ADMIN_ID,))
    conn.commit()
    conn.close()
    # Добавить нового супер-админа с актуальным username
    add_user(ADMIN_ID, 'hermanshelekhov', role='admin')

init_super_admin()

def ensure_permissions_table():
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS permissions (
            user_id INTEGER,
            cabinet_id INTEGER,
            has_access INTEGER DEFAULT 1,
            PRIMARY KEY (user_id, cabinet_id)
        )
    ''')
    conn.commit()
    conn.close()

ensure_permissions_table()

def get_user_permissions(user_id):
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('SELECT cabinet_id, has_access FROM permissions WHERE user_id = ?', (user_id,))
    rows = c.fetchall()
    conn.close()
    return {row[0]: bool(row[1]) for row in rows}

def set_user_permission(user_id, cabinet_id, has_access):
    print(f"[DEBUG] set_user_permission: user_id={user_id}, cabinet_id={cabinet_id}, has_access={has_access}")
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO permissions (user_id, cabinet_id, has_access)
        VALUES (?, ?, ?)
    ''', (user_id, cabinet_id, int(has_access)))
    conn.commit()
    conn.close()

def get_all_permissions():
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('SELECT user_id, cabinet_id, has_access FROM permissions')
    rows = c.fetchall()
    conn.close()
    return rows

def get_user_by_id(user_id: int):
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('SELECT user_id, username, role, is_active FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_all_cabinets():
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('SELECT id, name FROM cabinets')
    rows = c.fetchall()
    conn.close()
    return [{'id': row[0], 'name': row[1]} for row in rows]

def add_global_cabinet(name: str):
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('INSERT INTO cabinets (name) VALUES (?)', (name,))
    conn.commit()
    conn.close()

def remove_cabinet_by_index(user_id: int, cabinet_index: int) -> bool:
    """Удаляет кабинет по индексу для пользователя."""
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('SELECT id FROM cabinets WHERE user_id = ? ORDER BY id', (user_id,))
    rows = c.fetchall()
    if 0 <= cabinet_index < len(rows):
        cab_id = rows[cabinet_index][0]
        c.execute('DELETE FROM cabinets WHERE id = ?', (cab_id,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def update_cabinet_name_by_index(user_id: int, cabinet_index: int, new_name: str) -> bool:
    """Обновляет имя кабинета по индексу для пользователя."""
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('SELECT id FROM cabinets WHERE user_id = ? ORDER BY id', (user_id,))
    rows = c.fetchall()
    if 0 <= cabinet_index < len(rows):
        cab_id = rows[cabinet_index][0]
        c.execute('UPDATE cabinets SET name = ? WHERE id = ?', (new_name, cab_id))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

async def get_accessible_cabinets(user_id):
    print(f"[DEBUG] get_accessible_cabinets: user_id={user_id}")
    import sqlite3
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('SELECT * FROM permissions WHERE user_id = ?', (user_id,))
    perms = c.fetchall()
    print(f"[DEBUG] permissions for user {user_id}: {perms}")
    conn.close()
    async with async_session() as session:
        stmt = select(Cabinet).join(Permission, Cabinet.id == Permission.cabinet_id).where(
            Permission.user_id == user_id,
            Permission.has_access == 1
        )
        result = await session.execute(stmt)
        cabinets = result.scalars().all()
        print(f"[DEBUG] accessible cabinets for user {user_id}: {[c.name for c in cabinets]}")
        return cabinets 

def remove_cabinet_by_id(cabinet_id: int) -> bool:
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    # Удаляем связанные permissions
    c.execute('DELETE FROM permissions WHERE cabinet_id = ?', (cabinet_id,))
    # Удаляем сам кабинет
    c.execute('DELETE FROM cabinets WHERE id = ?', (cabinet_id,))
    conn.commit()
    conn.close()
    return True 