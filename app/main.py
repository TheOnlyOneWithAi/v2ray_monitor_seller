import asyncio
import logging

import uvicorn

from .config import settings

log = logging.getLogger(__name__)


async def run_bot_safely() -> None:
    from .bot import build_bot
    runner = build_bot()
    await runner.start()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    if not settings.token or not settings.admins:
        settings.setup_interactive()
        settings.validate_runtime()

    from .api import app
    from .db import init_db
    await init_db()

    bot_task = asyncio.create_task(run_bot_safely(), name="seller-bot")
    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=settings.web_port, log_level="info"))
    server_task = asyncio.create_task(server.serve(), name="seller-web")
    done, pending = await asyncio.wait({bot_task, server_task}, return_when=asyncio.FIRST_EXCEPTION)
    for task in done:
        exc = task.exception()
        if exc:
            log.error("seller task failed: %s", exc, exc_info=exc)
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
