"""app.config 模块测试（含 SecretStr + .env 加载）。"""
from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr


def test_settings_default_secret_is_empty():
    """默认 SecretStr 是空，不抛错也不暴露明文。"""
    from app.config import Settings
    s = Settings()
    assert isinstance(s.llm_api_key, SecretStr)
    assert s.get_llm_api_key() == ""
    assert "sk-" not in repr(s.llm_api_key)


def test_settings_secret_value_uses_get_secret_value():
    """取值必须显式调用 get_secret_value()。"""
    from app.config import Settings
    s = Settings(llm_api_key="sk-test-12345")
    assert s.get_llm_api_key() == "sk-test-12345"
    assert repr(s.llm_api_key) == "SecretStr('**********')"


def test_settings_repr_does_not_leak_secrets():
    from app.config import Settings
    s = Settings(
        llm_api_key="sk-test-12345",
        paddleocr_token="paddle-secret-abc",
    )
    text = repr(s)
    assert "sk-test-12345" not in text
    assert "paddle-secret-abc" not in text


def test_settings_load_from_env_file(tmp_path: Path, monkeypatch):
    """从 .env 文件加载配置（含 SecretStr）。"""
    from app.config import Settings

    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_API_KEY=sk-from-env-9999\n"
        "PADDLEOCR_TOKEN=ocr-from-env-8888\n",
        encoding="utf-8",
    )
    s = Settings(_env_file=str(env_file))
    assert s.get_llm_api_key() == "sk-from-env-9999"
    assert s.get_paddleocr_token() == "ocr-from-env-8888"


def test_settings_path_properties_are_absolute():
    from app.config import Settings
    s = Settings()
    assert s.db_path.is_absolute()
    assert s.raw_path.is_absolute()
    assert s.prompts_path.is_absolute()
    assert s.uploads_path.is_absolute()
    assert s.outputs_path.is_absolute()
    assert s.backups_path.is_absolute()


def test_settings_db_path_relative_to_project_root():
    from app.config import PROJECT_ROOT, Settings
    s = Settings(database_path="custom/db.sqlite")
    assert s.db_path == PROJECT_ROOT / "custom" / "db.sqlite"
