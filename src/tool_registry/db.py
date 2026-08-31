from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from tool_registry.config import load_db_config


class Base(DeclarativeBase):
    pass


db = load_db_config()
engine = create_async_engine(
    f"postgresql+psycopg://{db.user}:{db.password}@{db.host}:{db.port}/{db.name}",
    echo=False,
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables() -> None:
    import tool_registry.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def test_connection() -> None:
    async with engine.connect() as connection:
        result = await connection.execute(
            text("""
                SELECT
                    current_database(),
                    current_user
            """)
        )
        row = result.one()

        print(f"database={row[0]} user={row[1]}")
