"""提示词加载器测试。"""
from __future__ import annotations

import time

import pytest

from app.services import prompt_loader


def test_load_prompt_reads_file(tmp_prompts_dir):
    content = prompt_loader.load_prompt("test_prompt", prompts_dir=tmp_prompts_dir)
    assert content == "hello {{ name }}\n"


def test_load_prompt_accepts_dot_txt(tmp_prompts_dir):
    content = prompt_loader.load_prompt("test_prompt.txt", prompts_dir=tmp_prompts_dir)
    assert content == "hello {{ name }}\n"


def test_load_prompt_missing_raises(tmp_prompts_dir):
    with pytest.raises(FileNotFoundError, match="test_prompt_missing"):
        prompt_loader.load_prompt("test_prompt_missing", prompts_dir=tmp_prompts_dir)


def test_load_prompt_uses_mtime_cache(tmp_prompts_dir):
    prompt_loader.clear_cache()
    a = prompt_loader.load_prompt("test_prompt", prompts_dir=tmp_prompts_dir)
    b = prompt_loader.load_prompt("test_prompt", prompts_dir=tmp_prompts_dir)
    assert a == b


def test_load_prompt_reloads_on_mtime_change(tmp_prompts_dir):
    prompt_loader.clear_cache()
    a = prompt_loader.load_prompt("test_prompt", prompts_dir=tmp_prompts_dir)

    time.sleep(0.05)
    target = tmp_prompts_dir / "test_prompt.txt"
    target.write_text("updated content", encoding="utf-8")

    b = prompt_loader.load_prompt("test_prompt", prompts_dir=tmp_prompts_dir)
    assert a != b
    assert b == "updated content\n"


def test_clear_cache_forces_reload(tmp_prompts_dir):
    prompt_loader.load_prompt("test_prompt", prompts_dir=tmp_prompts_dir)
    prompt_loader.clear_cache()
    a = prompt_loader.load_prompt("test_prompt", prompts_dir=tmp_prompts_dir)
    assert a == "hello {{ name }}\n"
