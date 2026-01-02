"""
Async database session management using SQLAlchemy 2.0.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

# Create async engine with connection pooling
async_engine = create_async_engine(
    settings.async_database_url,
    echo=settings.app_debug,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Create async session factory
async_session_maker = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides an async database session.
    
    Usage:
        @app.get("/items")
        async def get_items(session: AsyncSession = Depends(get_async_session)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

