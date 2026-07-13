"""questions 路由集成测试。"""
from __future__ import annotations


def test_list_questions_default_returns_html(client_with_questions):
    r = client_with_questions.get("/questions")
    assert r.status_code == 200
    body = r.text
    assert "<html" in body
    assert "题库浏览" in body
    assert "<select" in body


def test_list_questions_with_filter(client_with_questions):
    r = client_with_questions.get("/questions?grade=七年级")
    assert r.status_code == 200
    body = r.text
    # 行要么存在（七年级匹配），要么是空状态
    assert ("M2024-NCZK-1" in body) or ("无匹配题目" in body)


def test_list_questions_htmx_returns_fragment(client_with_questions):
    r = client_with_questions.get(
        "/questions", headers={"HX-Request": "true"}
    )
    assert r.status_code == 200
    body = r.text
    assert "<html" not in body  # 片段不含 html


def test_list_questions_non_htmx_returns_full_page(client_with_questions):
    r = client_with_questions.get("/questions")
    assert "<html" in r.text


def test_list_questions_illegal_param_does_not_crash(client_with_questions):
    r = client_with_questions.get("/questions?grade=六年级&year=99999")
    assert r.status_code == 200


def test_list_questions_pagination_param(client_with_questions):
    r = client_with_questions.get("/questions?page=1")
    assert r.status_code == 200


def test_detail_question_found(client_with_questions):
    r = client_with_questions.get("/questions/M2024-NCZK-1")
    assert r.status_code == 200
    body = r.text
    assert "题干1" in body
    assert "答案1" in body
    assert "解析1" in body


def test_detail_question_not_found_returns_404(client_with_questions):
    r = client_with_questions.get("/questions/M2099-NOPE-1")
    assert r.status_code == 404


def test_detail_question_invalid_id_returns_404(client_with_questions):
    r = client_with_questions.get("/questions/not-a-valid-id")
    assert r.status_code == 404


def test_detail_question_404_body_has_code(client_with_questions):
    """spec 3.2 要求 404 body 形如 {detail, code}。"""
    r = client_with_questions.get("/questions/M2099-NOPE-1")
    assert r.status_code == 404
    body = r.json()
    assert body == {"detail": "题目不存在", "code": "not_found"}


def test_detail_question_back_link(client_with_questions):
    r = client_with_questions.get("/questions/M2024-NCZK-1")
    assert r.status_code == 200
    assert "/questions" in r.text  # 返回列表链接
