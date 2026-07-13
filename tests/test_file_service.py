"""文件服务（路径安全）测试。"""
from __future__ import annotations

import pytest

from app.services import file_service


def test_raw_path_is_under_raw():
    raw = file_service.settings.raw_path / "2024-NCZK.pdf"
    assert file_service.is_under_raw(raw) is True


def test_uploads_path_is_under_writable():
    p = file_service.settings.uploads_path / "tmp.pdf"
    assert file_service.is_under_writable_root(p) is True


def test_outputs_path_is_under_writable():
    p = file_service.settings.outputs_path / "paper.html"
    assert file_service.is_under_writable_root(p) is True


def test_unknown_path_is_not_writable(tmp_path):
    p = tmp_path / "outside.db"
    assert file_service.is_under_writable_root(p) is False


def test_assert_writable_rejects_raw():
    raw_target = file_service.settings.raw_path / "tries_to_delete.pdf"
    with pytest.raises(PermissionError, match="raw/"):
        file_service.assert_writable(raw_target)


def test_assert_writable_rejects_outside_whitelist(tmp_path):
    target = tmp_path / "outside" / "file.txt"
    with pytest.raises(PermissionError, match="白名单"):
        file_service.assert_writable(target)


def test_assert_writable_accepts_uploads():
    target = file_service.settings.uploads_path / "ok.pdf"
    resolved = file_service.assert_writable(target)
    assert resolved.exists() is False


def test_safe_join_stays_under_root():
    root = file_service.settings.uploads_path
    p = file_service.safe_join(root, "subdir", "file.pdf")
    assert p.is_relative_to(root)


def test_safe_join_rejects_traversal():
    root = file_service.settings.uploads_path
    with pytest.raises(PermissionError, match="越界"):
        file_service.safe_join(root, "..", "..", "etc", "passwd")


def test_safe_join_handles_empty_parts():
    root = file_service.settings.uploads_path
    p = file_service.safe_join(root)
    assert p == root.resolve()
