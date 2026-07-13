"""scripts.init_db 模块测试。"""
from __future__ import annotations

import json

import pytest


def test_reset_database_removes_all_suffixes(tmp_path, monkeypatch):
    db = tmp_path / "vault.db"
    for suffix in ("", "-journal", "-wal", "-shm"):
        p = db.with_name(db.name + suffix) if suffix else db
        p.write_bytes(b"data")
    assert db.exists()

    from app.config import Settings
    from scripts import init_db as init_db_module

    test_settings = Settings(database_path=str(db))
    monkeypatch.setattr(init_db_module, "settings", test_settings)

    init_db_module.reset_database()
    for suffix in ("", "-journal", "-wal", "-shm"):
        p = db.with_name(db.name + suffix) if suffix else db
        assert not p.exists(), f"{p} should be deleted"


def test_seed_knowledge_tree_writes_nodes(tmp_path, monkeypatch):
    db = tmp_path / "vault.db"
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    seed = [
        {"id": "n1", "name": "节点 1", "code": "N1", "sort_order": 1},
        {"id": "n2", "name": "节点 2", "parent_id": "n1"},
    ]
    (prompts / "knowledge_tree_seed.json").write_text(
        json.dumps(seed, ensure_ascii=False), encoding="utf-8"
    )

    from app.config import Settings
    from app.database import init_schema
    from scripts import init_db as init_db_module

    test_settings = Settings(database_path=str(db), prompts_dir=str(prompts))
    monkeypatch.setattr(init_db_module, "settings", test_settings)
    init_schema(db_path=db)

    count = init_db_module.seed_knowledge_tree()
    assert count == 2


def test_seed_knowledge_tree_missing_file_is_noop(tmp_path, monkeypatch):
    db = tmp_path / "vault.db"
    prompts = tmp_path / "prompts"
    prompts.mkdir()

    from app.config import Settings
    from app.database import init_schema
    from scripts import init_db as init_db_module

    test_settings = Settings(database_path=str(db), prompts_dir=str(prompts))
    monkeypatch.setattr(init_db_module, "settings", test_settings)
    init_schema(db_path=db)

    count = init_db_module.seed_knowledge_tree()
    assert count == 0


def test_seed_knowledge_tree_rejects_non_array(tmp_path, monkeypatch):
    db = tmp_path / "vault.db"
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "knowledge_tree_seed.json").write_text('{"not": "array"}', encoding="utf-8")

    from app.config import Settings
    from app.database import init_schema
    from scripts import init_db as init_db_module

    test_settings = Settings(database_path=str(db), prompts_dir=str(prompts))
    monkeypatch.setattr(init_db_module, "settings", test_settings)
    init_schema(db_path=db)

    with pytest.raises(ValueError, match="数组"):
        init_db_module.seed_knowledge_tree()


def test_seed_knowledge_tree_rejects_node_missing_fields(tmp_path, monkeypatch):
    db = tmp_path / "vault.db"
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "knowledge_tree_seed.json").write_text(
        '[{"id": "x"}]', encoding="utf-8"
    )

    from app.config import Settings
    from app.database import init_schema
    from scripts import init_db as init_db_module

    test_settings = Settings(database_path=str(db), prompts_dir=str(prompts))
    monkeypatch.setattr(init_db_module, "settings", test_settings)
    init_schema(db_path=db)

    with pytest.raises(ValueError, match="id/name"):
        init_db_module.seed_knowledge_tree()


def test_main_reset_requires_yes_flag(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr("sys.argv", ["init_db.py", "--reset"])
    from scripts import init_db as init_db_module

    with caplog.at_level("ERROR"):
        with pytest.raises(SystemExit) as exc:
            init_db_module.main()
    assert exc.value.code == 2
    assert "--yes" in caplog.text
