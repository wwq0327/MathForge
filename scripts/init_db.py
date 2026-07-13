"""初始化 MathForge 数据库。

执行内容：
1. 建表（knowledge_tree / papers / passages / questions / generated_papers）
2. （可选）从 prompts/knowledge_tree_seed.json 灌入知识树种子
3. （可选）灌入约 25 道示例题到 questions 表
4. 打印建表结果与表行数

用法：
    python scripts/init_db.py                # 仅建表
    python scripts/init_db.py --seed         # 建表 + 灌入知识树种子
    python scripts/init_db.py --demo         # 建表 + 灌入示例题（不重建库）
    python scripts/init_db.py --reset --yes  # 删除旧库后重建（需 --yes 确认）
    python scripts/init_db.py --reset --yes --demo  # 重建库 + 灌入示例题
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.config import settings  # noqa: E402
from app.database import ALLOWED_TABLES, get_connection, init_schema  # noqa: E402
from app.logging_config import configure as configure_logging  # noqa: E402
from app.logging_config import get_logger  # noqa: E402

configure_logging(log_dir=settings.db_path.parent, level="INFO")
log = get_logger("init_db")


def _seed_file() -> Path:
    """当前 settings 对应的种子文件路径（运行时计算，方便测试隔离）。"""
    return settings.prompts_path / "knowledge_tree_seed.json"


def reset_database() -> None:
    """删除现有数据库文件（先做 WAL checkpoint 再删，避免丢最后的事务）。"""
    db_path = settings.db_path
    for suffix in ("", "-journal", "-wal", "-shm"):
        p = db_path.with_name(db_path.name + suffix) if suffix else db_path
        if p.exists():
            p.unlink()
            log.info("已删除: %s", p)
        else:
            log.debug("跳过（不存在）: %s", p)


def seed_knowledge_tree() -> int:
    """从种子文件灌入知识点树。返回写入条数。"""
    seed_path = _seed_file()
    if not seed_path.exists():
        log.warning("种子文件不存在: %s，跳过", seed_path)
        return 0
    nodes = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(nodes, list):
        raise ValueError("种子文件根节点必须是数组")

    count = 0
    with get_connection() as conn:
        for node in nodes:
            if not isinstance(node, dict) or "id" not in node or "name" not in node:
                raise ValueError(f"节点缺 id/name: {node}")
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
    log.info("知识树已写入 %d 个节点", count)
    return count


def show_tables() -> None:
    """列出已建表及其行数。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        log.info("当前表清单：")
        for (name,) in rows:
            if name not in ALLOWED_TABLES:
                continue
            count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            log.info("  - %-20s %6d rows", name, count)


def main() -> None:
    parser = argparse.ArgumentParser(description="MathForge 数据库初始化")
    parser.add_argument("--reset", action="store_true", help="删除旧库后重建")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="配合 --reset，跳过交互确认（脚本化场景使用）",
    )
    parser.add_argument("--seed", action="store_true", help="灌入知识树种子")
    parser.add_argument("--demo", action="store_true", help="灌入示例题种子（约 25 道）")
    args = parser.parse_args()

    if args.reset:
        if not args.yes:
            log.error("--reset 是破坏性操作，请同时传 --yes 确认")
            log.error("示例: python scripts/init_db.py --reset --yes --seed")
            sys.exit(2)
        reset_database()

    init_schema()
    log.info("表结构已写入: %s", settings.db_path)

    if args.seed:
        seed_knowledge_tree()

    if args.demo:
        from app.services.demo_seed import seed_demo_questions

        n = seed_demo_questions()
        log.info("示例题已写入 %d 条", n)

    show_tables()
    log.info("数据库初始化完成")


if __name__ == "__main__":
    main()
