from pathlib import Path


INSTRUCTIONS = Path("integration/CHATGPT_INSTRUCTIONS.md").read_text(encoding="utf-8")


def test_dongqiudi_live_review_is_post_ready_and_advisory():
    assert "post-READY advisory review" in INSTRUCTIONS
    assert "not production-wired into the collector" in INSTRUCTIONS
    assert "must not overwrite the frozen Stable V3.5.1" in INSTRUCTIONS
    assert "external_review=INSUFFICIENT" in INSTRUCTIONS


def test_dongqiudi_fixture_identity_is_not_name_only():
    assert "date + league + kickoff + both teams" in INSTRUCTIONS
    assert "Team-name equality alone is insufficient" in INSTRUCTIONS
    assert "ambiguous" in INSTRUCTIONS
    assert "post-kickoff" in INSTRUCTIONS


def test_dongqiudi_review_separates_draw_types():
    assert "natural draw candidate" in INSTRUCTIONS
    assert "upset-type draw" in INSTRUCTIONS
    assert "strongest natural draw candidates and score(s)" in INSTRUCTIONS
    assert "strongest upset candidates and score(s)" in INSTRUCTIONS
