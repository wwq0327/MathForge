"""papers 路由集成测试。

覆盖（设计文档 §8）：
- POST /api/cart/toggle 200 / 404（题目不存在）
- POST /api/cart/clear 200（C1 回归：TemplateResponse 签名）
- GET /api/cart/summary 200
- GET /papers/new 200（空 cart / 有 cart）
- POST /papers 302 + Location
- GET /papers/{id} 200 / 404
- GET /papers/{id}/preview 200
- GET /papers/{id}/export/html 200 + Content-Disposition
- GET /papers/{id}/export/latex 200 + Content-Type=application/x-tex
"""
from __future__ import annotations


def test_cart_toggle_add(client_with_questions):
    """添加 cart 返回 200，bar 片段显示 1 题。"""
    r = client_with_questions.post("/api/cart/toggle?question_id=M2024-NCZK-1")
    assert r.status_code == 200
    body = r.text
    assert "已选" in body
    assert "<strong" in body and ">1</strong>" in body


def test_cart_toggle_remove(client_with_questions):
    """再次 toggle 移除，bar 显示 0 题。"""
    client_with_questions.post("/api/cart/toggle?question_id=M2024-NCZK-1")
    r = client_with_questions.post("/api/cart/toggle?question_id=M2024-NCZK-1")
    assert r.status_code == 200
    assert ">0</strong>" in r.text


def test_cart_toggle_nonexistent_returns_404(client_with_questions):
    """C2 回归：toggle 不存在题返回 404 JSON。"""
    r = client_with_questions.post("/api/cart/toggle?question_id=M9999-NOPE-1")
    assert r.status_code == 404
    assert r.json()["code"] == "not_found"


def test_cart_summary_empty(client_with_questions):
    """空 cart 摘要返回 0 题。"""
    r = client_with_questions.get("/api/cart/summary")
    assert r.status_code == 200
    assert ">0</strong>" in r.text


def test_cart_summary_with_items(client_with_questions):
    """加 2 题后摘要显示 2 题。"""
    client_with_questions.post("/api/cart/toggle?question_id=M2024-NCZK-1")
    client_with_questions.post("/api/cart/toggle?question_id=M2024-NCZK-2")
    r = client_with_questions.get("/api/cart/summary")
    assert r.status_code == 200
    assert ">2</strong>" in r.text


def test_cart_clear_returns_200(client_with_questions):
    """C1 回归：cart_clear 端点使用新 TemplateResponse 签名，调用 200。"""
    client_with_questions.post("/api/cart/toggle?question_id=M2024-NCZK-1")
    r = client_with_questions.post("/api/cart/clear")
    assert r.status_code == 200
    assert ">0</strong>" in r.text
    r2 = client_with_questions.get("/api/cart/summary")
    assert ">0</strong>" in r2.text


def test_papers_new_empty_cart(client_with_questions):
    """空 cart 访问组卷页返回 200，提示先选题。"""
    r = client_with_questions.get("/papers/new")
    assert r.status_code == 200
    assert "购物车为空" in r.text or "去选题" in r.text


def test_papers_new_with_cart(client_with_questions):
    """有 cart 时显示已选题。"""
    client_with_questions.post("/api/cart/toggle?question_id=M2024-NCZK-1")
    client_with_questions.post("/api/cart/toggle?question_id=M2024-NCZK-2")
    r = client_with_questions.get("/papers/new")
    assert r.status_code == 200
    body = r.text
    assert "题干1" in body
    assert "题干2" in body


def test_papers_generate_success(client_with_questions):
    """POST /papers 生成试卷返回 303 + Location。"""
    client_with_questions.post("/api/cart/toggle?question_id=M2024-NCZK-1")
    r = client_with_questions.post(
        "/papers",
        data={"title": "测试卷", "answer_mode": "0", "format": "html"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "/papers/" in r.headers["location"]


def test_papers_generate_empty_cart_redirects_back(client_with_questions):
    """空 cart 提交 → 重定向回 /papers/new。"""
    r = client_with_questions.post(
        "/papers",
        data={"title": "空", "answer_mode": "0", "format": "html"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/papers/new"


def test_papers_result_found(client_with_questions):
    """GET /papers/{id} 存在时返回 200。"""
    client_with_questions.post("/api/cart/toggle?question_id=M2024-NCZK-1")
    r = client_with_questions.post(
        "/papers",
        data={"title": "测试卷", "answer_mode": "0", "format": "html"},
        follow_redirects=False,
    )
    paper_id = r.headers["location"].rsplit("/", 1)[-1]
    r2 = client_with_questions.get(f"/papers/{paper_id}")
    assert r2.status_code == 200
    assert "测试卷" in r2.text


def test_papers_result_not_found(client_with_questions):
    """GET /papers/{id} 不存在返回 404 JSON。"""
    r = client_with_questions.get("/papers/99999")
    assert r.status_code == 404
    assert r.json()["code"] == "not_found"


def test_papers_preview_returns_html(client_with_questions):
    """preview 返回 HTML 200。"""
    client_with_questions.post("/api/cart/toggle?question_id=M2024-NCZK-1")
    r = client_with_questions.post(
        "/papers",
        data={"title": "测试卷", "answer_mode": "0", "format": "html"},
        follow_redirects=False,
    )
    paper_id = r.headers["location"].rsplit("/", 1)[-1]
    r2 = client_with_questions.get(f"/papers/{paper_id}/preview")
    assert r2.status_code == 200
    assert "text/html" in r2.headers["content-type"]


def test_papers_export_html(client_with_questions):
    """export/html 返回 200 + Content-Disposition 附件。"""
    client_with_questions.post("/api/cart/toggle?question_id=M2024-NCZK-1")
    r = client_with_questions.post(
        "/papers",
        data={"title": "测试卷", "answer_mode": "0", "format": "html"},
        follow_redirects=False,
    )
    paper_id = r.headers["location"].rsplit("/", 1)[-1]
    r2 = client_with_questions.get(f"/papers/{paper_id}/export/html")
    assert r2.status_code == 200
    assert "attachment" in r2.headers["content-disposition"]
    assert ".html" in r2.headers["content-disposition"]


def test_papers_export_latex(client_with_questions):
    """export/latex 返回 200 + application/x-tex + .tex 附件。"""
    client_with_questions.post("/api/cart/toggle?question_id=M2024-NCZK-1")
    r = client_with_questions.post(
        "/papers",
        data={"title": "测试卷", "answer_mode": "0", "format": "html"},
        follow_redirects=False,
    )
    paper_id = r.headers["location"].rsplit("/", 1)[-1]
    r2 = client_with_questions.get(f"/papers/{paper_id}/export/latex")
    assert r2.status_code == 200
    assert r2.headers["content-type"] == "application/x-tex"
    assert ".tex" in r2.headers["content-disposition"]


def test_papers_export_latex_title_escaped(client_with_questions):
    """C3 回归：含特殊字符的标题导出时正确转义。"""
    client_with_questions.post("/api/cart/toggle?question_id=M2024-NCZK-1")
    special_title = "My & Title 100% $test"
    r = client_with_questions.post(
        "/papers",
        data={"title": special_title, "answer_mode": "0", "format": "html"},
        follow_redirects=False,
    )
    paper_id = r.headers["location"].rsplit("/", 1)[-1]
    r2 = client_with_questions.get(f"/papers/{paper_id}/export/latex")
    body = r2.text
    assert r"\&" in body
    assert r"\%" in body
    assert r"\$" in body
    assert "My & Title 100% $test" not in body


def test_papers_export_404(client_with_questions):
    """不存在的 paper_id export 返回 404。"""
    r = client_with_questions.get("/papers/99999/export/html")
    assert r.status_code == 404
    r2 = client_with_questions.get("/papers/99999/export/latex")
    assert r2.status_code == 404
