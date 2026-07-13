"""提示词加载器。

设计要点（PLAN.md 设计原则 6）：
- 提示词存为 .txt 外部文件，代码不硬编码
- 支持热重载：mtime 缓存，文件变化时自动重新读取
- 文件缺失抛明确错误（开发期暴露，运维期不静默）
"""
from __future__ import annotations

from pathlib import Path

from ..config import settings
from ..logging_config import get_logger

log = get_logger("prompts")


_cache: dict[str, tuple[float, str]] = {}


def load_prompt(name: str, *, prompts_dir: Path | None = None) -> str:
    """按文件名加载提示词（不含扩展名，自动补 .txt）。

    Args:
        name: 文件名（不含 .txt），例 ``"ocr_prompt"`` → 读 ``prompts/ocr_prompt.txt``
        prompts_dir: 自定义目录；默认从 settings.prompts_path

    Returns:
        文件内容（已 strip 尾部空白）

    Raises:
        FileNotFoundError: 提示词文件不存在
    """
    if not name.endswith(".txt"):
        name = f"{name}.txt"

    root = prompts_dir or settings.prompts_path
    path = root / name

    if not path.exists():
        log.error("提示词文件缺失: %s", path)
        raise FileNotFoundError(f"提示词文件不存在: {path}")

    mtime = path.stat().st_mtime
    cached = _cache.get(name)
    if cached and cached[0] == mtime:
        return cached[1]

    content = path.read_text(encoding="utf-8").rstrip() + "\n"
    _cache[name] = (mtime, content)
    log.debug("加载提示词: %s (%d 字符)", name, len(content))
    return content


def clear_cache() -> None:
    """清空 mtime 缓存。供测试与运维显式刷新使用。"""
    _cache.clear()
