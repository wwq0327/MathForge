"""自定义 Pydantic 类型：JSON 数组字符串。

数据库存储为 TEXT（JSON 数组），应用层按需解析为 ``list[str]``。
"""
from __future__ import annotations

import builtins
import json
from typing import Any, Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class JsonListStr(str):
    """数据库存为 JSON 数组字符串，``.list`` 暴露解析后列表。

    Examples:
        >>> v = JsonListStr('["a.png", "b.png"]')
        >>> v.list
        ['a.png', 'b.png']
        >>> JsonListStr.from_list(["a", "b"])
        '["a", "b"]'
        >>> JsonListStr("not json")  # 构造时即校验
        Traceback (most recent ValueError: ...
    """

    @property
    def list(self) -> list[str]:
        """解析为字符串列表。"""
        return json.loads(self)

    @classmethod
    def from_list(cls, items: builtins.list[str]) -> Self:
        """从列表构造（自动序列化）。"""
        return cls(json.dumps(items, ensure_ascii=False))

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.str_schema(),
        )

    @classmethod
    def _validate(cls, value: str) -> Self:
        if not isinstance(value, str):
            raise TypeError(f"JsonListStr 须为 str，得到 {type(value).__name__}")
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JsonListStr 不是合法 JSON: {exc}") from exc
        if not isinstance(parsed, list):
            raise ValueError("JsonListStr 必须是 JSON 数组")
        if not all(isinstance(x, str) for x in parsed):
            raise ValueError("JsonListStr 元素必须全部为字符串")
        return cls(value)
