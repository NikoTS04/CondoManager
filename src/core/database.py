"""Capa de persistencia y configuración de SQLAlchemy 2.0 Async."""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from src.core.config import settings

# Engine asíncrono para PostgreSQL / asyncpg (o fallback SQLite para tests).
# En TESTING se usa NullPool: cada sesión abre y cierra su propia conexión dentro del
# mismo event loop, evitando que una conexión agregada al pool quede ligada al loop de
# una petición anterior (TestClient crea un portal/event loop por request).
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    poolclass=NullPool if settings.TESTING else None,
)

# Fábrica de sesiones asíncronas
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Clase base declarativa para todos los modelos ORM de la aplicación."""
    pass


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Inyector de dependencias FastAPI para obtener sesiones de base de datos."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
