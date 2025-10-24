from __future__ import annotations

from app.domain.models.EntityIDModel import QuestID
from app.infra.serialization import to_bson


def test_to_bson_excludes_legacy_number_field() -> None:
	fresh_id = QuestID.parse("QUESA1B2C3")

	payload = to_bson(fresh_id)

	assert payload == {"value": "QUESA1B2C3", "prefix": "QUES"}


def test_to_bson_handles_legacy_numeric_ids() -> None:
	legacy_id = QuestID.parse("QUES1234")

	payload = to_bson(legacy_id)

	assert payload == {"value": "QUES1234", "prefix": "QUES"}
