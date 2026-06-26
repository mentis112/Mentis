import asyncio

from sqlalchemy import text

from app.db.session import engine


async def wait_for_db() -> None:
    last_error: Exception | None = None
    for attempt in range(1, 31):
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            print("Database is ready")
            return
        except Exception as exc:  # pragma: no cover - startup resilience
            last_error = exc
            print(f"Waiting for database ({attempt}/30): {exc}")
            await asyncio.sleep(2)

    raise RuntimeError("Database did not become ready in time") from last_error


if __name__ == "__main__":
    asyncio.run(wait_for_db())
