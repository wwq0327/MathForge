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

import uvicorn

from app.config import settings
from app.database import init_schema
from app.logging_config import configure as configure_logging
from app.logging_config import get_logger


PROJECT_ROOT = Path(__file__).resolve().parent
configure_logging(log_dir=settings.db_path.parent, level="INFO")
log = get_logger("run")


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
        log.error("缺少依赖: %s", ", ".join(missing))
        log.error("请先执行: pip install -r requirements.txt")
        sys.exit(1)


def ensure_database() -> None:
    """数据库不存在则自动建表 + 灌种子。"""
    if not settings.db_path.exists():
        log.info("数据库不存在，开始建表: %s", settings.db_path)
        init_schema()
        try:
            from scripts.init_db import seed_knowledge_tree
            seed_knowledge_tree()
        except Exception as exc:  # noqa: BLE001
            log.warning("知识树种子灌入失败（可忽略）: %s", exc)
    else:
        log.info("数据库已存在: %s", settings.db_path)


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

    log.info("MathForge 启动 → http://%s:%d", args.host, args.port)
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
