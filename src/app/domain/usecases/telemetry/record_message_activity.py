from datetime import datetime, timezone
from typing import Optional

async def record_message_activity(users_repo, user_id: str, category_id: Optional[int] = None) -> None:
  u = await users_repo.get(user_id)
  u.messages_count_total += 1
  u.last_active_at = datetime.now(timezone.utc)
  if category_id is not None:
    u.messages_count_by_category[category_id] = u.messages_count_by_category.get(category_id, 0) + 1
  await users_repo.upsert(u)