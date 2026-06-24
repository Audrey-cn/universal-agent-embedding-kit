# Changelog

## Unreleased

### Changed (red-team hardening 2026-06-24)
- capability matrix: 新增 `partial` provider 状态。旧 `_provider_status` 把任何未满分的 live 运行一律标 `blocked / 0.0` 并归因 "usage limit/lock"，把真实跑出的 mimo 9/10、hermes 8/10 谎报成"跑不通"。现如实报告真实 tasks_passed/capability_score；`blocked` 仅留给真正零通过的非执行。
- matrix/benchmark/audit JSON 按新口径重生成：**2 graded_live + 2 partial（blocked 0）**，headline 仍 98/partial（graded-live 门禁未放宽）。
- 文档补充诚实边界：跨 CLI ≠ 跨模型族（backends ≤3）；两 graded provider 间观测 spread = 0.0。

### Added (red-team hardening 2026-06-24)
- capability 评分器加 **held-out/变形用例**（封堵红队 #2 过拟合攻击）：`grade_code` 每题除固定公开用例外，再跑 16 个由可信参考实现生成、provider 未见过的确定性随机输入。写死查找表只过公开用例、必挂 held-out（控制实验 overfit lookup 1/19 fail，正确解 19/19 pass）。
- 重评已捕获 provider 解的证据 `benchmarks/results/capability-heldout-regrade.json`：claude_code/codex 在 held-out 下仍 10/10（证明当前数字非过拟合），mimo 9/10、hermes 8/10 不变，headline 2/4 graded-live / 98 partial 不受影响。
- 3 个新测试锁定 held-out 行为（抓 overfit、确定性、参考实现匹配公开用例）。

## 0.1.0 (2026-06-20)

### Added
- 初始 UAEK 核心框架：verification / effort / workflow / memory / skills / harness
- CLI (`uaek`) + HTTP API + MCP server 三层暴露
- 5 个研究命题全部有本地证据（rung 3-4）：
  - 命题1 自适应上下文管理（70% 利用率 0.85 期望准确率）
  - 命题2 对抗验证（作弊率 naive 71% → adversarial 0%）
  - 命题3 成本模型（建模 -49%；live warm 抽检 -82% 仅作为 best-case 证据；100% TTL miss 冷路径 +22% 成本）
  - 命题4 真实场景基准（40 场景 38 类别，多维评分抓回归，每个错误解都有区分用例）
  - 命题5 跨平台能力矩阵（2/4 provider full-suite graded-live；Mimo/Hermes partial artifacts 保留）
- 400 个单元测试，ruff / mypy 全绿
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
