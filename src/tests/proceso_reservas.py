"""Cliente ASGI en proceso nuevo; usado exclusivamente por pruebas CON-80."""

import asyncio
import json
import os
import sys

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.core.database import get_db_session
from src.main import app


async def main():
    datos = json.loads(sys.stdin.read())
    engine = create_async_engine(
        os.environ["DATABASE_URL"], poolclass=NullPool,
        connect_args={"server_settings": {"search_path": datos["esquema"]}},
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def session():
        async with sessions() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    app.dependency_overrides[get_db_session] = session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.request(**datos["request"])
            print(json.dumps({"pid": os.getpid(), "status": response.status_code,
                              "body": response.json()}))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
