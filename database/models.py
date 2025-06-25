from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, String, DateTime
import datetime

DATABASE_URL = "sqlite+aiosqlite:///db.sqlite3"

Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Cabinet(Base):
    __tablename__ = 'cabinets'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True)
    name = Column(String)
    client_id = Column(String)
    client_secret = Column(String)
    advertiser_id = Column(String)

class AvitoToken(Base):
    __tablename__ = 'avito_tokens'
    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    client_secret = Column(String)
    access_token = Column(String)
    expires_at = Column(DateTime)

class Permission(Base):
    __tablename__ = 'permissions'
    user_id = Column(Integer, primary_key=True)
    cabinet_id = Column(Integer, primary_key=True)
    has_access = Column(Integer, default=1) 