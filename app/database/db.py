import os

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
import dotenv
from urllib.parse import quote_plus

dotenv.load_dotenv()


_DATABASE_URL: str | None = None
_engine = None
_session_factory: async_sessionmaker | None = None


def _build_database_url() -> str:
    """Получить (и при необходимости сформировать) строку подключения."""
    global _DATABASE_URL
    if _DATABASE_URL:
        return _DATABASE_URL

    url = os.getenv("DATABASE_URL", None)
    if not url:
        user = os.getenv("POSTGRES_USER", "app")
        pwd = os.getenv("POSTGRES_PASSWORD", "change_me")
        host = os.getenv("POSTGRES_HOST", "postgres")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "appdb")
        # Percent-encode credentials to handle special characters
        user_enc = quote_plus(user)
        pwd_enc = quote_plus(pwd)
        url = f"postgresql+asyncpg://{user_enc}:{pwd_enc}@{host}:{port}/{db}"

    _DATABASE_URL = url
    return _DATABASE_URL


def get_engine():
    """Лениво создать async engine в текущем event loop."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            _build_database_url(),
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10
        )
    return _engine


def get_session_factory():
    """Лениво создать async_sessionmaker, привязанный к engine."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
        )
    return _session_factory


class LazyAsyncSessionmaker:
    def __call__(self, *args, **kwargs):
        return get_session_factory()(*args, **kwargs)


Base = declarative_base()

AsyncSessionLocal = LazyAsyncSessionmaker()


async def get_session():
    """Async generator to be used as dependency in FastAPI and elsewhere.

    Usage in FastAPI:
        async def endpoint(session: AsyncSession = Depends(get_session)):
            await session.execute(...)

    It yields an AsyncSession and ensures proper commit/close by caller.
    """
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    # Import models so they are registered with Base.metadata
    try:
        from . import models  # noqa: F401
    except Exception:
        # Fallback for different import contexts
        import importlib
        importlib.import_module('database.models')

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Явно экспортируем строку подключения для alembic и других скриптов.
DATABASE_URL = _build_database_url()
