from app.infra.mongo.characters_repo import CharactersRepoMongo
from app.infra.mongo.quests_repo import QuestsRepoMongo
from app.infra.mongo.summaries_repo import SummariesRepoMongo
from app.infra.mongo.users_repo import UsersRepoMongo

user_repo = UsersRepoMongo()
chars_repo = CharactersRepoMongo()
quests_repo = QuestsRepoMongo()
summaries_repo = SummariesRepoMongo()
