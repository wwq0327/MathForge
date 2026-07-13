"""MathForge 一键启动脚本。

行为：
1. 确保依赖已安装（缺失则提示）
2. 确保数据库已初始化（不存在则自动建表 + 灌种子）
3. 启动 Uvicorn

用法：
    python run.py                # 默认配置启动
    python run.py --port 8080    # 自定义端口
    python run.py --no-init      # 跳过自动初始化
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402
from app.database import init_schema  # noqa: E402


def ensure_dependencies() -> None:
    """检查关键依赖是否可导入。"""
    required = ("fastapi", "uvicorn", "jinja2", "pydantic", "pydantic_settings")
    missing = []
    for module in required:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        print(f"[error] 缺少依赖: {', '.join(missing)}")
        print("请先执行: pip install -r requirements.txt")
        sys.exit(1)


def ensure_database() -> None:
    """数据库不存在则自动建表 + 灌种子。"""
    if not settings.db_path.exists():
        print(f"[init] 数据库不存在，开始建表: {settings.db_path}")
        init_schema()
        try:
            from scripts.init_db import seed_knowledge_tree
            seed_knowledge_tree()
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] 知识树种子灌入失败（可忽略）: {exc}")
    else:
        print(f"[init] 数据库已存在: {settings.db_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="MathForge 启动器")
    parser.add_argument("--host", default=settings.app_host)
    parser.add_argument("--port", type=int, default=settings.app_port)
    parser.add_argument("--reload", action="store_true", default=settings.app_debug)
    parser.add_argument("--no-init", action="store_true", help="跳过自动初始化")
    args = parser.parse_args()

    ensure_dependencies()
    if not args.no_init:
        ensure_database()

    import uvicorn
    print(f"\n[run] MathForge 启动 → http://{args.host}:{args.port}\n")
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
