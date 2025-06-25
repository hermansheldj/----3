import asyncio
import pytest
from database.models import async_session, Cabinet, Permission
from database.crud import get_user_cabinets, set_user_permission

@pytest.mark.asyncio
async def test_get_user_cabinets(tmp_path):
    # Подготовка тестовых данных
    async with async_session() as session:
        # Создаём два кабинета
        cab1 = Cabinet(user_id=1, name="Кабинет 1", client_id="c1", client_secret="s1", advertiser_id="a1")
        cab2 = Cabinet(user_id=2, name="Кабинет 2", client_id="c2", client_secret="s2", advertiser_id="a2")
        session.add_all([cab1, cab2])
        await session.commit()
        # Достаём id кабинетов
        await session.refresh(cab1)
        await session.refresh(cab2)
        # Выдаём пользователю 3 доступ к cab2
        perm = Permission(user_id=3, cabinet_id=cab2.id, has_access=1)
        session.add(perm)
        await session.commit()

    # Проверяем: пользователь 1 видит только свой кабинет
    cabs1 = await get_user_cabinets(1)
    assert any(c.name == "Кабинет 1" for c in cabs1)
    assert not any(c.name == "Кабинет 2" for c in cabs1)

    # Проверяем: пользователь 3 видит только выданный через permissions кабинет
    cabs3 = await get_user_cabinets(3)
    assert any(c.name == "Кабинет 2" for c in cabs3)
    assert not any(c.name == "Кабинет 1" for c in cabs3)

    # Проверяем: пользователь 2 видит только свой кабинет
    cabs2 = await get_user_cabinets(2)
    assert any(c.name == "Кабинет 2" for c in cabs2)
    assert not any(c.name == "Кабинет 1" for c in cabs2)

    # Проверяем: если выдать пользователю 1 доступ к cab2, он видит оба
    await set_user_permission(1, cab2.id, True)
    cabs1b = await get_user_cabinets(1)
    assert any(c.name == "Кабинет 1" for c in cabs1b)
    assert any(c.name == "Кабинет 2" for c in cabs1b) 