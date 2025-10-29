from app.infra.db import close_client, get_client, ping


async def on_startup():
    get_client()
    await ping()


async def on_shutdown():
    await close_client()
