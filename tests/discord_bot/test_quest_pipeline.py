from __future__ import annotations

from datetime import timezone

from app.bot.ingestion.pipeline import parse_message, validate


def test_parse_handles_custom_quest_announcement() -> None:
    raw = (
        "# <:gw:1284189726378823751> Pawluck Finale Episode 4: The Echoes of War\n"
        "Choose a faction to help and combat the Voice's schemes behind it all\n\n"
        "Currently Available PoIs:\n"
        "G1 - Yeshara\n"
        "~~G2~~/P2 - Greentide\n"
        "A3/~~G3~~ - Grundholm\n"
        "H2/P3 - Southeast of Tallvane\n"
        "A2/H3 - Old Widow's Woods\n\n"
        "**Goal**: Peace\n"
        "**Reward**: Kushal gets to finally rest\n\n"
        "## 🔸 Game Information\n"
        "**Region:** Pawluck Valley\n\n"
        "**Tags:** `Region Storyline` `Finale` `Player Choice Driven` `Combat` `RP`\n\n"
        "**Scheduling & Duration:** <t:1759505400:F>, 3-4 hour duration\n\n"
        "**My table:** https://discord.com/channels/1278898468970299523/1285899555711356978\n\n"
        "**Linked Quests:** https://discord.com/channels/1278898468970299523/1419930053872979969\n\n"
        "<@&1301848054827319409> \n"
        "### Players\n"
        "-\n\n"
        "https://discord.gg/livingchronicles?event=1423380915115262115\n"
    )

    parsed = parse_message(
        raw=raw,
        referee_discord_id="98765",
        guild_id=12345,
        channel_id=54321,
        message_id=99999,
    )

    # ensure schedule parsing found a future timestamp
    assert parsed.starts_at_utc.tzinfo == timezone.utc
    assert parsed.duration_minutes >= 180

    validate(parsed)

    assert parsed.title.startswith("Pawluck Finale Episode 4")
    assert parsed.region_name == "Pawluck Valley"
    assert parsed.linked_messages == [
        ("1278898468970299523", "1285899555711356978", "1419930053872979969")
    ]
    assert parsed.event_url.startswith("https://discord.gg")
    assert parsed.raw == raw

    # ensure quest metadata preserved after validation run
    assert parsed.discord_channel_id == str(54321)
    assert parsed.discord_message_id == str(99999)
    assert parsed.referee_discord_id == "98765"

    # parsed end time should be after start even with flexible duration parsing
    assert parsed.ends_at_utc > parsed.starts_at_utc

    # derived times should be within 4 hours of each other for the provided range
    assert (parsed.ends_at_utc - parsed.starts_at_utc).total_seconds() <= 4 * 60 * 60
