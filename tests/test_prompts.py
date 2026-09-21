from app.prompts import ACTIVE_PROMPT_IDS, ALL_PROMPTS, PROMPTS


def test_every_active_prompt_id_has_a_prompt():
    assert set(ACTIVE_PROMPT_IDS) <= set(ALL_PROMPTS)


def test_prompts_are_the_active_subset_in_order():
    assert list(PROMPTS) == ACTIVE_PROMPT_IDS
    assert all(PROMPTS[prompt_id] == ALL_PROMPTS[prompt_id] for prompt_id in PROMPTS)


def test_the_full_suite_of_40_prompts_runs():
    assert list(PROMPTS) == [f"{n:02d}" for n in range(1, 41)]
    assert all(text.strip() for text in PROMPTS.values())
