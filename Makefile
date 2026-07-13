# MathForge 开发命令
# 用法：make <target>

.PHONY: help install run reset test lint format typecheck clean all

help:
	@echo "MathForge 命令："
	@echo "  make install     - 安装运行时 + 开发依赖"
	@echo "  make run         - 启动服务（自动建库）"
	@echo "  make reset       - 重置数据库（需 yes 确认）"
	@echo "  make test        - 运行 pytest + 覆盖率"
	@echo "  make lint        - ruff check"
	@echo "  make format      - ruff check --fix"
	@echo "  make typecheck   - mypy app/"
	@echo "  make clean       - 清理缓存"
	@echo "  make all         - lint + typecheck + test"

install:
	pip install -r requirements.txt -r requirements-dev.txt

run:
	python run.py

reset:
	python scripts/init_db.py --reset --yes --seed

test:
	pytest --cov=app --cov-report=term-missing

lint:
	ruff check .

format:
	ruff check . --fix

typecheck:
	mypy app/

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

all: lint typecheck test
