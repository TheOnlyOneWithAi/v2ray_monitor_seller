from .config import settings
from .db import init_db
from .bot import build_bot
from .web import app
import asyncio
import uvicorn

async def main():
    await init_db()
    bot_task = asyncio.create_task(build_bot().start())
    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=settings.web_port, log_level="info"))
    try:
        await server.serve()
    finally:
        bot_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
