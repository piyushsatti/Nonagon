from datetime import datetime, timezone
from typing import Iterable

async def record_event_attendance(users_repo, user_ids: Iterable[str]) -> None:
  now = datetime.now(timezone.utc)
  for uid in user_ids:
    u = await users_repo.get(uid)
    u.events_attended += 1
    u.last_active_at = now
    await users_repo.upsert(u)