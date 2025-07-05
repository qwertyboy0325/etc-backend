"""Database configuration and connection management."""

import logging
from typing import AsyncGenerator

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Create async engine for database operations
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,
)

# Create sync engine for Alembic migrations
sync_engine = create_engine(
    settings.DATABASE_URL.replace("+asyncpg", ""),
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,
    autocommit=False,
)

# Create sync session factory for migrations
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine,
)

# Define metadata with naming convention for constraints
metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)

# Create declarative base
Base = declarative_base(metadata=metadata)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async dependency to get database session.

    Yields:
        AsyncSession: Database session instance.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


# Alias for compatibility
get_db = get_async_session


def get_sync_session():
    """
    Sync dependency to get database session for migrations.

    Yields:
        Session: Database session instance.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


async def init_db() -> None:
    """Initialize database connection and create tables if needed."""
    try:
        # Test connection
        async with async_engine.begin() as conn:
            logger.info("Database connection established successfully")

            # In development, you might want to create tables here
            # await conn.run_sync(Base.metadata.create_all)

    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


async def close_db() -> None:
    """Close database connections."""
    try:
        await async_engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")


# Database health check function
async def check_db_health() -> bool:
    """
    Check database connectivity.

    Returns:
        bool: True if database is healthy, False otherwise.
    """
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            result.fetchone()
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
