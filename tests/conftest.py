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
from collections.abc import Callable
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


def _make_client(
    isolated_settings, monkeypatch, seed_fn: Callable | None = None
):
    """构造 FastAPI TestClient；可选 seed_fn(conn) 在建表后灌种子。"""
    from app import config as config_module
    from app import database as database_module
    from app import logging_config as logging_module
    from app import main as main_module

    monkeypatch.setattr(config_module, "settings", isolated_settings)
    importlib.reload(database_module)
    importlib.reload(logging_module)
    importlib.reload(main_module)

    logging_module.configure(
        log_dir=isolated_settings.db_path.parent, level="WARNING"
    )
    database_module.init_schema(db_path=isolated_settings.db_path)

    if seed_fn is not None:
        with database_module.get_connection() as conn:
            seed_fn(conn)

    return TestClient(main_module.app)


@pytest.fixture
def client(isolated_settings, monkeypatch):
    """FastAPI TestClient，使用隔离配置。"""
    with _make_client(isolated_settings, monkeypatch) as c:
        yield c


def _seed_minimal(conn) -> None:
    """灌入 2 个顶层知识点 + 3 道覆盖多维度的题目。"""
    conn.executemany(
        "INSERT INTO knowledge_tree (id, name) VALUES (?, ?)",
        [("kt-num", "数与代数"), ("kt-fig", "图形与几何")],
    )
    conn.executemany(
        """INSERT INTO questions (
            id, stage, grade, question_type, section, source, source_abbr,
            year, review_status, topic_l1, difficulty, stem, answer, solution
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            ("M2024-NCZK-1", "初中", "七年级", "选择题", "数与代数", "测试A", "NCZK",
             2024, "已入库", "kt-num", "易", "题干1", "答案1", "解析1"),
            ("M2024-NCZK-2", "初中", "七年级", "填空题", "数与代数", "测试A", "NCZK",
             2024, "草稿", "kt-num", "中", "题干2", "答案2", "解析2"),
            ("M2024-BJMS-1", "初中", "八年级", "计算题", "图形与几何", "测试B", "BJMS",
             2024, "已入库", "kt-fig", "难", "题干3", "答案3", "解析3"),
        ],
    )


@pytest.fixture
def client_with_questions(isolated_settings, monkeypatch):
    """client 的扩展版，自动灌入 2 知识点 + 3 道覆盖多维度的题目。"""
    with _make_client(isolated_settings, monkeypatch, seed_fn=_seed_minimal) as c:
        yield c
