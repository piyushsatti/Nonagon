from app.infra.db import get_client, ping, close_client

async def on_startup():
  get_client()
  await ping()

async def on_shutdown():
  await close_client()
