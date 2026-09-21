from app.prompts import ACTIVE_PROMPT_IDS, ALL_PROMPTS, PROMPTS


def test_every_active_prompt_id_has_a_prompt():
    assert set(ACTIVE_PROMPT_IDS) <= set(ALL_PROMPTS)


def test_prompts_are_the_active_subset_in_order():
    assert list(PROMPTS) == ACTIVE_PROMPT_IDS
    assert all(PROMPTS[prompt_id] == ALL_PROMPTS[prompt_id] for prompt_id in PROMPTS)


def test_only_prompt_01_runs_until_the_suite_is_enabled():
    assert ACTIVE_PROMPT_IDS == ["01"]
