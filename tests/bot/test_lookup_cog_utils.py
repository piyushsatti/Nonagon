from __future__ import annotations

from datetime import datetime, timezone

from app.bot.cogs.LookupCommandsCog import LookupListView, _build_lookup_embed
from app.domain.models.LookupModel import LookupEntry


def test_build_lookup_embed_includes_timestamp() -> None:
    entry = LookupEntry(
        guild_id=1,
        name="Guide",
        url="https://example.com/guide",
        created_by=10,
        created_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    entry.touch_updated(20, at=datetime(2030, 1, 2, tzinfo=timezone.utc))

    embed = _build_lookup_embed(entry)

    assert embed.title == "Guide"
    assert embed.fields[0].value == "https://example.com/guide"
    assert "Updated by <@20>" in embed.fields[1].value


def test_lookup_list_view_paginates() -> None:
    entries = [
        LookupEntry(
            guild_id=1,
            name=f"Doc {idx}",
            url=f"https://example.com/{idx}",
            created_by=1,
            created_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
        for idx in range(12)
    ]
    view = LookupListView(entries, "Guild", per_page=5)

    embed = view.render_embed()

    assert embed.footer.text == "Page 1 of 3"
    assert len(embed.fields) == 5

    view.page = 2
    view._sync_button_states()
    embed_last = view.render_embed()
    assert embed_last.footer.text == "Page 3 of 3"
    assert len(embed_last.fields) == 2
