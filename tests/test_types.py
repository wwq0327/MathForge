"""自定义 Pydantic 类型测试。"""
from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from app.models.types import JsonListStr


class _Model(BaseModel):
    images: JsonListStr


def test_from_list_round_trip():
    m = _Model(images=JsonListStr.from_list(["a.png", "b.png"]))
    assert m.images == '["a.png", "b.png"]'
    assert m.images.list == ["a.png", "b.png"]


def test_accepts_json_string():
    m = _Model(images='["x.jpg"]')
    assert m.images.list == ["x.jpg"]


def test_rejects_invalid_json():
    with pytest.raises(ValidationError, match="JSON"):
        _Model(images="not json")


def test_rejects_json_object():
    with pytest.raises(ValidationError, match="数组"):
        _Model(images='{"a": 1}')


def test_rejects_json_array_of_non_strings():
    with pytest.raises(ValidationError, match="字符串"):
        _Model(images="[1, 2, 3]")


def test_empty_array():
    m = _Model(images="[]")
    assert m.images.list == []


def test_persists_through_model_dump():
    m = _Model(images=JsonListStr.from_list(["a", "b"]))
    dumped = m.model_dump()
    assert dumped["images"] == '["a", "b"]'
