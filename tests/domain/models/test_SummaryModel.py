# tests/domain/models/test_summary.py
from datetime import datetime, timedelta

from app.domain.models.quest.SummaryModel import QuestSummary, SummaryKind


# ─────────────────────────────────────────────────────────────
# 1) Construction & safe defaults
# ─────────────────────────────────────────────────────────────
def test_summary_defaults_are_safe():
    s = QuestSummary(
        summary_id="s1",
        quest_id="q1",
        author_user_id="u1",
        kind=SummaryKind.PLAYER,
        summary_text="We delved into the crypt.",
        posted_at=datetime.utcnow(),
    )

    assert s.is_private is False
    assert s.audience_roles == []
    assert s.tags == []
    assert s.reactions == {}
    assert s.edited_at is None
    assert s.edited_by is None


# ─────────────────────────────────────────────────────────────
# 2) Mutable defaults are not shared across instances
# (lists/dicts should be independent per object)
# ─────────────────────────────────────────────────────────────
def test_mutable_defaults_not_shared():
    s1 = QuestSummary(
        summary_id="s1",
        quest_id="q1",
        author_user_id="u1",
        kind=SummaryKind.PLAYER,
        summary_text="First",
        posted_at=datetime.utcnow(),
    )
    s2 = QuestSummary(
        summary_id="s2",
        quest_id="q1",
        author_user_id="u2",
        kind=SummaryKind.PLAYER,
        summary_text="Second",
        posted_at=datetime.utcnow(),
    )

    s1.tags.append("boss-fight")
    s1.reactions["like"] = 3
    s1.audience_roles.append("admin")

    assert s2.tags == []
    assert s2.reactions == {}
    assert s2.audience_roles == []


# ─────────────────────────────────────────────────────────────
# 3) Kind & visibility flags (DM summaries can be private)
# ─────────────────────────────────────────────────────────────
def test_dm_summary_can_be_private_with_audience_roles():
    s = QuestSummary(
        summary_id="dm1",
        quest_id="q42",
        author_user_id="u_dm",
        kind=SummaryKind.DM,
        summary_text="Behind-the-screen notes.",
        posted_at=datetime.utcnow(),
        is_private=True,
        audience_roles=["admin", "referee"],
    )
    assert s.kind is SummaryKind.DM
    assert s.is_private is True
    assert set(s.audience_roles) == {"admin", "referee"}


# ─────────────────────────────────────────────────────────────
# 4) Edit metadata is optional and type-safe
# ─────────────────────────────────────────────────────────────
def test_edit_metadata_can_be_set_later():
    s = QuestSummary(
        summary_id="s1",
        quest_id="q1",
        author_user_id="u1",
        kind=SummaryKind.PLAYER,
        summary_text="v1",
        posted_at=datetime.utcnow(),
    )

    # simulate an edit
    s.summary_text = "v2 - fixed typos"
    s.edited_at = datetime.utcnow()
    s.edited_by = "u1"

    assert isinstance(s.edited_at, datetime)
    assert s.edited_by == "u1"
    assert "v2" in s.summary_text


# ─────────────────────────────────────────────────────────────
# 5) Simple reactions bookkeeping example (no helpers in model)
# ─────────────────────────────────────────────────────────────
def test_reactions_counter_patterns():
    s = QuestSummary(
        summary_id="s1",
        quest_id="q1",
        author_user_id="u1",
        kind=SummaryKind.PLAYER,
        summary_text="Great table vibes.",
        posted_at=datetime.utcnow(),
    )

    # increment pattern juniors will see in services
    s.reactions["like"] = s.reactions.get("like", 0) + 1
    s.reactions["like"] = s.reactions.get("like", 0) + 1
    s.reactions["star"] = s.reactions.get("star", 0) + 1

    assert s.reactions["like"] == 2
    assert s.reactions["star"] == 1


# ─────────────────────────────────────────────────────────────
# 6) Basic linkage & types sanity
# ─────────────────────────────────────────────────────────────
def test_identity_and_linkage_fields():
    now = datetime.utcnow()
    s = QuestSummary(
        summary_id="sum-123",
        quest_id="quest-abc",
        author_user_id="user-xyz",
        kind=SummaryKind.PLAYER,
        summary_text="Short recap.",
        posted_at=now,
    )
    assert s.summary_id == "sum-123"
    assert s.quest_id == "quest-abc"
    assert s.author_user_id == "user-xyz"
    assert s.posted_at is now
