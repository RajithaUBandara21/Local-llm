import importlib

from app import config
from app.config import load_setting, read_env_file


def test_missing_env_file_gives_no_values(tmp_path):
    assert read_env_file(tmp_path / ".env") == {}


def test_env_file_skips_blanks_comments_and_lines_without_equals(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("# a comment\n\nOLLAMA_URL=http://host:1\nnot a setting\n", encoding="utf-8")

    assert read_env_file(env_file) == {"OLLAMA_URL": "http://host:1"}


def test_env_file_strips_whitespace_and_one_pair_of_matching_quotes(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "  A = spaced  \nB=\"double\"\nC='single'\nD=\"mismatched'\nE=\n", encoding="utf-8"
    )

    assert read_env_file(env_file) == {
        "A": "spaced",
        "B": "double",
        "C": "single",
        "D": "\"mismatched'",
        "E": "",
    }


def test_env_file_splits_on_the_first_equals_sign(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("URL=http://host/?a=b\n", encoding="utf-8")

    assert read_env_file(env_file) == {"URL": "http://host/?a=b"}


def test_setting_falls_back_to_default(tmp_path, monkeypatch):
    monkeypatch.delenv("SAMPLE_SETTING", raising=False)

    assert load_setting("SAMPLE_SETTING", "fallback", tmp_path / ".env") == "fallback"


def test_setting_prefers_env_file_over_default(tmp_path, monkeypatch):
    monkeypatch.delenv("SAMPLE_SETTING", raising=False)
    (tmp_path / ".env").write_text("SAMPLE_SETTING=from-file\n", encoding="utf-8")

    assert load_setting("SAMPLE_SETTING", "fallback", tmp_path / ".env") == "from-file"


def test_setting_prefers_real_environment_over_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SAMPLE_SETTING", "from-environment")
    (tmp_path / ".env").write_text("SAMPLE_SETTING=from-file\n", encoding="utf-8")

    assert load_setting("SAMPLE_SETTING", "fallback", tmp_path / ".env") == "from-environment"


def test_env_file_with_a_bom_keeps_its_first_key(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_bytes(b"\xef\xbb\xbfOLLAMA_URL=http://host:1\n")

    assert read_env_file(env_file) == {"OLLAMA_URL": "http://host:1"}


def test_unreadable_env_file_gives_no_values(tmp_path):
    utf16_file = tmp_path / "utf16.env"
    utf16_file.write_text("OLLAMA_URL=http://host:1\n", encoding="utf-16")
    directory = tmp_path / "dir.env"
    directory.mkdir()

    assert read_env_file(utf16_file) == {}
    assert read_env_file(directory) == {}


def test_base_url_loses_its_trailing_slash_and_derives_the_generate_url(monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://host:1/")
    try:
        reloaded = importlib.reload(config)
        assert reloaded.OLLAMA_URL == "http://host:1"
        assert reloaded.OLLAMA_GENERATE_URL == "http://host:1/api/generate"
    finally:
        monkeypatch.undo()
        importlib.reload(config)
