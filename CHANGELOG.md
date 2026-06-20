# Changelog

## 0.1.0 (2026-06-20)

### Added
- 初始 UAEK 核心框架：verification / effort / workflow / memory / skills / harness
- CLI (`uaek`) + HTTP API + MCP server 三层暴露
- 5 个研究命题全部有本地证据（rung 3-4）：
  - 命题1 自适应上下文管理（70% 利用率 0.85 期望准确率）
  - 命题2 对抗验证（作弊率 naive 71% → adversarial 0%）
  - 命题3 成本模型（建模 -49%；live warm 抽检 -82% 仅作为 best-case 证据；100% TTL miss 冷路径 +22% 成本）
  - 命题4 真实场景基准（30 场景 28 类别，多维评分抓回归，每个错误解都有区分用例）
  - 命题5 跨平台能力矩阵（2/4 provider full-suite graded-live；Mimo/Hermes partial artifacts 保留）
- 396 个单元测试，ruff / mypy 全绿
- 14+ benchmark JSON 证据归档
- `uaek audit` / `benchmark --suite all` 聚合入口
- CI workflow（quality gates + release-gate）
- Wheel build (`dist/uaek-0.1.0-py3-none-any.whl`)；license metadata 使用非弃用 SPDX 字符串口径

### Known Limitations
- 最新本地修改仍需远端 GitHub Actions 复跑并绑定运行记录
- 未发布到 PyPI
- Fable 5 baseline 已撤回 — 使用 proxy validation + live provider evidence
- 场景语料 10 个（seed 规模），非 100+ live multi-hour 会话
- Claude Code CLI 路由 mimo-v2.5-pro，模型后端 ≤3 互异
