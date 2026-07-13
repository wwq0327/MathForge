"""pytest 全局夹具。

设计要点：
- 隔离临时数据库（tmp_path fixture 自动提供）
- 隔离临时 prompts 目录
- 隔离临时 .env 文件
- 提供 FastAPI TestClient

实现：通过临时 .env 文件传递配置，避免污染工作目录。
"""
from __future__ import annotations

import importlib
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _cleanup_test_dirs():
    """每个测试后清理可能误创建在 cwd 的 test_* 目录（防御性）。"""
    yield
    cwd = Path.cwd()
    for p in cwd.glob("test_*"):
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """返回临时数据库路径。"""
    return tmp_path / "vault.db"


@pytest.fixture
def tmp_prompts_dir(tmp_path: Path) -> Path:
    """创建临时 prompts 目录，含一个测试用 prompt 文件。"""
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "test_prompt.txt").write_text("hello {{ name }}", encoding="utf-8")
    return prompts


@pytest.fixture
def isolated_settings(
    tmp_path: Path, tmp_db_path: Path, tmp_prompts_dir: Path, monkeypatch
):
    """构造隔离的 Settings 实例，不影响全局 ``settings``。"""
    test_env = tmp_path / ".env"
    test_env.write_text(
        f"APP_DEBUG=false\n"
        f"DATABASE_PATH={tmp_db_path}\n"
        f"PROMPTS_DIR={tmp_prompts_dir}\n",
        encoding="utf-8",
    )

    from app import config as config_module

    original_env_file = config_module.Settings.model_config["env_file"]
    config_module.Settings.model_config["env_file"] = str(test_env)
    try:
        test_settings = config_module.Settings()
        yield test_settings
    finally:
        config_module.Settings.model_config["env_file"] = original_env_file


@pytest.fixture
def client(isolated_settings, monkeypatch):
    """FastAPI TestClient，使用隔离配置。"""
    from app import config as config_module

    monkeypatch.setattr(config_module, "settings", isolated_settings)

    from app import database as database_module
    from app import logging_config as logging_module
    from app import main as main_module

    importlib.reload(database_module)
    importlib.reload(logging_module)
    importlib.reload(main_module)

    logging_module.configure(log_dir=isolated_settings.db_path.parent, level="WARNING")
    database_module.init_schema(db_path=isolated_settings.db_path)

    with TestClient(main_module.app) as c:
        yield c
