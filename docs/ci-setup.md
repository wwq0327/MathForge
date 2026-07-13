# CI 配置说明

CI 配置文件 `.github/workflows/ci.yml` 已在本地就绪，但推送时遇到 GitHub OAuth scope 限制：

```
! [remote rejected] main -> main (refusing to allow an OAuth App to create or
update workflow `.github/workflows/ci.yml` without `workflow` scope)
```

## 解决方案

需要给 `gh` 授权添加 `workflow` scope：

```bash
gh auth refresh -h github.com -s workflow
# 或在浏览器中手动添加
# https://github.com/settings/tokens → 勾选 "workflow"
```

## 临时方案

在获得 workflow scope 之前，CI 配置可手动在 GitHub 网页上添加：
1. 进入 https://github.com/wwq0327/MathForge/actions
2. 点击 "set up a workflow yourself"
3. 粘贴 `.github/workflows/ci.yml` 内容
4. 提交

## 配置内容

文件已就绪，包含：
- 触发：push main / PR
- 矩阵：Python 3.11 / 3.12
- 步骤：install → ruff → mypy → pytest --cov
- 覆盖率 artifact 上传

## 相关 issue

#18 P2 CI workflow
