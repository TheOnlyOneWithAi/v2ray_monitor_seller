from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey, select
from datetime import datetime, timezone
from .config import settings

engine=create_async_engine(settings.database_url)
Session=async_sessionmaker(engine, expire_on_commit=False)
class Base(DeclarativeBase): pass
class Setting(Base):
    __tablename__='settings'
    key: Mapped[str]=mapped_column(String(100),primary_key=True)
    value: Mapped[str]=mapped_column(Text,default='')
class Plan(Base):
    __tablename__='plans'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    name: Mapped[str]=mapped_column(String(100))
    price: Mapped[int]=mapped_column(Integer)
    max_configs: Mapped[int]=mapped_column(Integer)
    days: Mapped[int]=mapped_column(Integer,default=30)
    active: Mapped[bool]=mapped_column(Boolean,default=True)
class User(Base):
    __tablename__='users'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    telegram_id: Mapped[int]=mapped_column(Integer,index=True,unique=True)
    username: Mapped[str]=mapped_column(String(255),default='')
    created_at: Mapped[datetime]=mapped_column(DateTime,default=lambda:datetime.now(timezone.utc))
class Order(Base):
    __tablename__='orders'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id'))
    plan_id: Mapped[int]=mapped_column(ForeignKey('plans.id'))
    status: Mapped[str]=mapped_column(String(30),default='pending')
    receipt: Mapped[str]=mapped_column(Text,default='')
    created_at: Mapped[datetime]=mapped_column(DateTime,default=lambda:datetime.now(timezone.utc))
    paid_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
class Subscription(Base):
    __tablename__='subscriptions'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id'))
    plan_id: Mapped[int]=mapped_column(ForeignKey('plans.id'))
    config_count: Mapped[int]=mapped_column(Integer,default=0)
    expires_at: Mapped[datetime]=mapped_column(DateTime)
    active: Mapped[bool]=mapped_column(Boolean,default=True)
async def init_db():
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    async with Session() as s:
        if not (await s.execute(select(Plan))).scalars().first():
            s.add_all([Plan(name='اقتصادی',price=99000,max_configs=3),Plan(name='استاندارد',price=199000,max_configs=10),Plan(name='پریمیوم',price=299000,max_configs=27)])
            await s.commit()
