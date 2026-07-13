r"""文件路径安全工具。

设计要点（PLAN.md 设计原则 4）：
- \`raw/\` 是源文件库，应用层禁止写入/删除
- 所有用户可控路径在落地前需经过本模块校验
"""
from __future__ import annotations

from pathlib import Path

from ..config import settings
from ..logging_config import get_logger

log = get_logger("file_service")


# 允许写入/删除的根目录（白名单）
WRITABLE_ROOTS: tuple[Path, ...] = (
    settings.uploads_path,
    settings.outputs_path,
    settings.backups_path,
    settings.prompts_path,
    settings.db_path.parent,
)


def is_under_writable_root(path: Path) -> bool:
    """判断 ``path`` 是否在白名单根目录下。"""
    resolved = path.resolve()
    return any(
        _is_parent(root, resolved) for root in WRITABLE_ROOTS
    )


def is_under_raw(path: Path) -> bool:
    """判断 ``path`` 是否在 raw/ 目录下（只读保护区）。"""
    resolved = path.resolve()
    raw_root = settings.raw_path.resolve()
    return _is_parent(raw_root, resolved)


def _is_parent(parent: Path, child: Path) -> bool:
    """判断 ``parent`` 是否是 ``child`` 的祖先路径。"""
    try:
        parent_resolved = parent.resolve()
        child.relative_to(parent_resolved)
        return True
    except ValueError:
        return False


def assert_writable(path: Path) -> Path:
    """断言 ``path`` 允许写入，返回解析后的绝对路径。

    Raises:
        PermissionError: 路径在 raw/ 下或不在白名单根目录
    """
    resolved = path.resolve()
    if is_under_raw(resolved):
        log.error("拒绝写入 raw/ 路径: %s", resolved)
        raise PermissionError(f"raw/ 是只读区，禁止写入: {resolved}")
    if not is_under_writable_root(resolved):
        log.error("拒绝写入非白名单路径: %s", resolved)
        raise PermissionError(f"路径不在可写白名单内: {resolved}")
    return resolved


def safe_join(root: Path, *parts: str) -> Path:
    """路径拼接 + 白名单校验。

    Raises:
        PermissionError: 拼接结果不在 root 下
    """
    candidate = (root / "/".join(parts)).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        log.error("路径越界: %s -> %s", root, candidate)
        raise PermissionError(f"路径越界: {candidate}") from exc
    return candidate
