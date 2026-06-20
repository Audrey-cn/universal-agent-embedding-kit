# Changelog

## 0.1.0 (2026-06-20)

### Added
- 初始 UAEK 核心框架：verification / effort / workflow / memory / skills / harness
- CLI (`uaek`) + HTTP API + MCP server 三层暴露
- 5 个研究命题全部有本地证据（rung 3-4）：
  - 命题1 自适应上下文管理（70% 利用率 0.85 期望准确率）
  - 命题2 对抗验证（作弊率 naive 71% → adversarial 0%）
  - 命题3 成本模型（建模 -49%，live warm 实测 -82%）
  - 命题4 真实场景基准（10 场景 9 类别，多维评分抓回归）
  - 命题5 跨平台能力矩阵（4/4 provider graded-live）
- 385 个单元测试，ruff / mypy 全绿
- 14+ benchmark JSON 证据归档
- `uaek audit` / `benchmark --suite all` 聚合入口
- CI workflow（quality gates + release-gate）
- Wheel build (`dist/uaek-0.1.0-py3-none-any.whl`)

### Known Limitations
- 无远端 GitHub Actions 运行记录（全部门禁仅本地验证）
- 未发布到 PyPI
- Fable 5 baseline 已撤回 — 使用 proxy validation + live provider evidence
- 场景语料 10 个（seed 规模），非 100+ live multi-hour 会话
- Claude Code CLI 路由 mimo-v2.5-pro，模型后端 ≤3 互异
