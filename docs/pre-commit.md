# Pre-commit

本地开发推荐使用 pre-commit 在提交前自动跑 lint / format / typecheck。

## 安装

```bash
pip install pre-commit
pre-commit install
```

之后每次 `git commit` 会自动跑：
- `ruff check --fix`：自动修复风格问题
- `ruff format`：格式化
- `mypy app/`：类型检查

## 手动运行

```bash
pre-commit run --all-files   # 跑所有文件
pre-commit run ruff          # 只跑 ruff
```

## 跳过

紧急情况下可跳过（不推荐）：
```bash
git commit --no-verify -m "..."
```

## 配置文件

- `.pre-commit-config.yaml`：本文件
- `pyproject.toml` [tool.ruff] / [tool.mypy]：实际规则

## CI

CI 在 PR 上跑相同检查（见 `.github/workflows/ci.yml`），不依赖 pre-commit 本地配置。
