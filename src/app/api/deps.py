# src/app/api/deps.py
from app.infra.db import get_db
from app.infra.users_repo import MongoUsersRepo
from app.infra.quests_repo import MongoQuestsRepo
from app.infra.summaries_repo import MongoSummariesRepo

def get_users_repo():
    return MongoUsersRepo(get_db())

def get_quests_repo():
    return MongoQuestsRepo(get_db())

def get_summaries_repo():
    return MongoSummariesRepo(get_db())
