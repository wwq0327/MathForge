"""Pydantic 模型测试。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.enums import Difficulty, QuestionType, ReviewStatus
from app.models.paper import PaperCreate
from app.models.passage import PassageCreate
from app.models.question import QuestionCreate
from app.models.types import JsonListStr


class TestQuestionId:
    def test_valid_id(self):
        q = QuestionCreate(id="M2024-NCZK-001")
        assert q.id == "M2024-NCZK-001"

    def test_missing_id_rejected(self):
        with pytest.raises(ValidationError):
            QuestionCreate()

    def test_lowercase_abbr_rejected(self):
        with pytest.raises(ValidationError):
            QuestionCreate(id="M2024-nczk-001")

    def test_short_year_rejected(self):
        with pytest.raises(ValidationError):
            QuestionCreate(id="M24-NCZK-001")

    def test_no_m_prefix_rejected(self):
        with pytest.raises(ValidationError):
            QuestionCreate(id="2024-NCZK-001")

    def test_no_seq_rejected(self):
        with pytest.raises(ValidationError):
            QuestionCreate(id="M2024-NCZK")


class TestPaperId:
    def test_valid_id(self):
        p = PaperCreate(id="2024-NCZK", title="2024 年南充中考")
        assert p.id == "2024-NCZK"

    def test_id_with_seq_rejected(self):
        with pytest.raises(ValidationError):
            PaperCreate(id="2024-NCZK-001", title="x")

    def test_lowercase_rejected(self):
        with pytest.raises(ValidationError):
            PaperCreate(id="2024-nczk", title="x")


class TestPassageId:
    def test_valid_id(self):
        p = PassageCreate(id="2024-NCZK-001")
        assert p.id == "2024-NCZK-001"

    def test_no_seq_rejected(self):
        with pytest.raises(ValidationError):
            PassageCreate(id="2024-NCZK")

    def test_m_prefix_rejected(self):
        with pytest.raises(ValidationError):
            PassageCreate(id="M2024-NCZK-001")


class TestEnums:
    def test_question_type_enum(self):
        q = QuestionCreate(
            id="M2024-NCZK-001", question_type=QuestionType.CALCULATION
        )
        # use_enum_values=True：模型存 .value 字符串
        assert q.question_type == QuestionType.CALCULATION.value

    def test_difficulty_enum(self):
        q = QuestionCreate(id="M2024-NCZK-001", difficulty=Difficulty.HARD)
        # use_enum_values=True：模型存 .value 字符串
        assert q.difficulty == Difficulty.HARD.value

    def test_invalid_enum_value_rejected(self):
        with pytest.raises(ValidationError):
            QuestionCreate(
                id="M2024-NCZK-001", question_type="不存在的题型"
            )

    def test_review_status_default(self):
        q = QuestionCreate(id="M2024-NCZK-001")
        assert q.review_status is ReviewStatus.DRAFT


class TestNumericConstraints:
    def test_year_too_old_rejected(self):
        with pytest.raises(ValidationError):
            QuestionCreate(id="M2024-NCZK-001", year=1800)

    def test_year_too_new_rejected(self):
        with pytest.raises(ValidationError):
            QuestionCreate(id="M2024-NCZK-001", year=2200)

    def test_negative_score_rejected(self):
        with pytest.raises(ValidationError):
            QuestionCreate(id="M2024-NCZK-001", score=-1)

    def test_score_over_100_rejected(self):
        with pytest.raises(ValidationError):
            QuestionCreate(id="M2024-NCZK-001", score=150)


class TestFromAttributes:
    def test_from_dict(self):
        """from_attributes=True 等价支持 dict 构造（与 Row 等行为对齐）。"""
        q = QuestionCreate.model_validate(
            {
                "id": "M2024-NCZK-001",
                "difficulty": "难",
                "review_status": "草稿",
            }
        )
        assert q.id == "M2024-NCZK-001"


class TestJsonListStrFields:
    """JsonListStr 接入 model 字段的端到端测试（#26）。"""

    def test_images_from_json_string(self):
        q = QuestionCreate(
            id="M2024-NCZK-001",
            images='["img1.png", "img2.png"]',
        )
        assert isinstance(q.images, JsonListStr)
        assert q.images.list == ["img1.png", "img2.png"]

    def test_images_from_list_via_from_list(self):
        imgs = JsonListStr.from_list(["a.png", "b.png"])
        q = QuestionCreate(id="M2024-NCZK-001", images=imgs)
        assert q.images.list == ["a.png", "b.png"]

    def test_images_none(self):
        q = QuestionCreate(id="M2024-NCZK-001")
        assert q.images is None

    def test_images_invalid_json_rejected(self):
        with pytest.raises(ValidationError):
            QuestionCreate(
                id="M2024-NCZK-001", images="not json"
            )

    def test_images_not_array_rejected(self):
        with pytest.raises(ValidationError):
            QuestionCreate(
                id="M2024-NCZK-001", images='{"key": "value"}'
            )

    def test_images_non_string_element_rejected(self):
        with pytest.raises(ValidationError):
            QuestionCreate(
                id="M2024-NCZK-001", images='["ok", 123]'
            )

    def test_core_literacy_from_json(self):
        q = QuestionCreate(
            id="M2024-NCZK-001",
            core_literacy='["数学运算", "直观想象"]',
        )
        assert q.core_literacy.list == ["数学运算", "直观想象"]

    def test_from_dict_preserves_jsonliststr(self):
        """从 sqlite.Row 来的 dict 应正确解析为 JsonListStr。"""
        q = QuestionCreate.model_validate(
            {
                "id": "M2024-NCZK-001",
                "images": '["x.png"]',
                "core_literacy": '["核心素养1"]',
            }
        )
        assert q.images.list == ["x.png"]
        assert q.core_literacy.list == ["核心素养1"]
