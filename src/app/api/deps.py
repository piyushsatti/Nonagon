from app.infra.db import get_db
from app.infra.repo.users_repo import MongoUsersRepo
from app.infra.repo.quests_repo import MongoQuestsRepo
from app.infra.repo.summaries_repo import MongoSummariesRepo

def get_users_repo():
    return MongoUsersRepo(get_db())

def get_quests_repo():
    return MongoQuestsRepo(get_db())

def get_summaries_repo():
    return MongoSummariesRepo(get_db())
