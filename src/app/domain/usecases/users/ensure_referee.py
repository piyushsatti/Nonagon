from app.domain.models.UserModel import UserId

async def ensure_referee(users_repo, user_id: UserId):
  u = await users_repo.get(user_id)
  u.enable_referee()
  await users_repo.upsert(u)
  return u