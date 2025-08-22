from app.domain.models.UserModel import UserId

async def ensure_player(users_repo, user_id: UserId):
  u = await users_repo.get(user_id)
  u.enable_player()
  await users_repo.upsert(u)
  return u