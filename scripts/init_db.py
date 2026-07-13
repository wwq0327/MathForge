"""初始化 MathForge 数据库。

执行内容：
1. 建表（knowledge_tree / papers / passages / questions / generated_papers）
2. （可选）从 prompts/knowledge_tree_seed.json 灌入知识树种子
3. 打印建表结果与表行数

用法：
    python scripts/init_db.py                # 仅建表
    python scripts/init_db.py --seed         # 建表 + 灌入知识树种子
    python scripts/init_db.py --reset        # 删除旧库后重建
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402
from app.database import SCHEMA_SQL, get_connection, init_schema  # noqa: E402


SEED_FILE = settings.prompts_path / "knowledge_tree_seed.json"


def reset_database() -> None:
    """删除现有数据库文件。"""
    db_path = settings.db_path
    for suffix in ("", "-journal", "-wal", "-shm"):
        p = db_path.with_name(db_path.name + suffix) if suffix else db_path
        if p.exists():
            p.unlink()
    print(f"[reset] 已删除: {db_path}")


def seed_knowledge_tree() -> int:
    """从种子文件灌入知识点树。返回写入条数。"""
    if not SEED_FILE.exists():
        print(f"[seed] 种子文件不存在: {SEED_FILE}，跳过")
        return 0
    nodes = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    if not isinstance(nodes, list):
        raise ValueError("种子文件根节点必须是数组")

    count = 0
    with get_connection() as conn:
        for node in nodes:
            conn.execute(
                """
                INSERT OR REPLACE INTO knowledge_tree
                    (id, parent_id, name, code, sort_order, description)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    node["id"],
                    node.get("parent_id"),
                    node["name"],
                    node.get("code"),
                    node.get("sort_order", 0),
                    node.get("description"),
                ),
            )
            count += 1
    print(f"[seed] 知识树已写入 {count} 个节点")
    return count


def show_tables() -> None:
    """列出已建表及其行数。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        print("\n[tables]")
        for (name,) in rows:
            count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            print(f"  - {name:<20} {count:>6} rows")


def main() -> None:
    parser = argparse.ArgumentParser(description="MathForge 数据库初始化")
    parser.add_argument("--reset", action="store_true", help="删除旧库后重建")
    parser.add_argument("--seed", action="store_true", help="灌入知识树种子")
    args = parser.parse_args()

    if args.reset:
        reset_database()

    init_schema()
    print(f"[init] 表结构已写入: {settings.db_path}")

    if args.seed:
        seed_knowledge_tree()

    show_tables()
    print("\n[done] 数据库初始化完成")


if __name__ == "__main__":
    main()
