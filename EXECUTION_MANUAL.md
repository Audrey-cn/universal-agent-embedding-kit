# UAEK 执行手册

> 完整的执行流程和验证标准
> 基于 universal-agent-workflow 技能协议

---

## 执行原则

### 1. 遵循 Operating Loop

每个任务都按以下流程执行：

```
Classify → Inspect → Plan → Execute → Verify → Report
```

### 2. 使用 Goal Ledger

- 每个 Phase 有明确的目标
- 目标状态：pending → active → complete
- 完成需要具体证据

### 3. 使用 Findings Ledger

- 发现问题时记录 findings
- 严重性：low / medium / high / critical
- 高危和严重问题必须解决后才能完成

### 4. 验证门控

- 每个 Phase 完成前必须通过验证
- 验证类型：test / build / lint / benchmark
- 验证失败必须修复后重新验证

---

## Phase 1：基础层（第 1-4 周）

### 目标

1. 验证框架 v1 — Python 库 + 3 种验证类型
2. Effort 引擎 v1 — Python 库 + 分类算法

### 任务清单

#### Week 1-2：验证框架

| 任务 | 产出 | 验证标准 | 状态 |
|------|------|----------|------|
| 1.1 设计验证接口 | `src/verify/interface.py` | 接口定义完整 | pending |
| 1.2 实现 test 验证 | `src/verify/test_runner.py` | 能运行 pytest 并返回结果 | pending |
| 1.3 实现 build 验证 | `src/verify/build_runner.py` | 能运行构建命令并返回结果 | pending |
| 1.4 实现 lint 验证 | `src/verify/lint_runner.py` | 能运行 linter 并返回结果 | pending |
| 1.5 实现全新上下文验证 | `src/verify/fresh_context.py` | 验证者不继承执行者上下文 | pending |
| 1.6 编写测试 | `tests/unit/test_verify.py` | 所有测试通过 | pending |
| 1.7 发布 v0.1.0 | PyPI 包 | 可安装并运行 | pending |

#### Week 3-4：Effort 引擎

| 任务 | 产出 | 验证标准 | 状态 |
|------|------|----------|------|
| 2.1 设计复杂度指标 | `src/effort/metrics.py` | 指标定义完整 | pending |
| 2.2 实现分类算法 | `src/effort/classifier.py` | 准确率 >80% | pending |
| 2.3 实现调度短语生成 | `src/effort/dispatch_phrases.py` | 中英文短语正确 | pending |
| 2.4 实现验证深度映射 | `src/effort/verification_depth.py` | 4 级深度映射正确 | pending |
| 2.5 编写测试 | `tests/unit/test_effort.py` | 所有测试通过 | pending |
| 2.6 发布 v0.2.0 | PyPI 包 | 可安装并运行 | pending |

### 验证方案

```bash
# 验证框架测试
python -m pytest tests/unit/test_verify.py -v
uaek verify tests/unit/test_verify.py --type test

# Effort 引擎测试
python -m pytest tests/unit/test_effort.py -v
uaek effort "implement auth module"
uaek effort "fix typo in README"
uaek effort "refactor authentication system with 10+ files"
```

### Phase 1 完成标准

- [ ] 验证框架在 3 个测试用例上正确工作
- [ ] Effort 引擎在 10 个任务上分类准确率 >80%
- [ ] Python 库可安装并运行
- [ ] 所有单元测试通过
- [ ] 文档完整

---

## Phase 2：编排层（第 5-8 周）

### 目标

1. 工作流引擎 v1 — 并行调度 + 任务 DAG
2. 技能加载器 v1 — 技能发现 + 加载机制

### 任务清单

#### Week 5-6：工作流引擎

| 任务 | 产出 | 验证标准 | 状态 |
|------|------|----------|------|
| 3.1 设计工作流接口 | `src/workflow/interface.py` | 接口定义完整 | pending |
| 3.2 实现任务 DAG | `src/workflow/dag.py` | DAG 解析正确 | pending |
| 3.3 实现并行调度 | `src/workflow/parallel.py` | 3 个并行任务正确执行 | pending |
| 3.4 实现顺序调度 | `src/workflow/sequential.py` | 顺序任务正确执行 | pending |
| 3.5 实现条件分支 | `src/workflow/conditional.py` | 条件分支正确执行 | pending |
| 3.6 编写测试 | `tests/unit/test_workflow.py` | 所有测试通过 | pending |
| 3.7 发布 v0.3.0 | PyPI 包 | 可安装并运行 | pending |

#### Week 7-8：技能加载器

| 任务 | 产出 | 验证标准 | 状态 |
|------|------|----------|------|
| 4.1 设计技能接口 | `src/skills/interface.py` | 接口定义完整 | pending |
| 4.2 实现技能发现 | `src/skills/discovery.py` | 能发现 SKILL.md 文件 | pending |
| 4.3 实现技能加载 | `src/skills/loader.py` | 能加载并解析技能 | pending |
| 4.4 实现技能执行 | `src/skills/executor.py` | 能执行技能并返回结果 | pending |
| 4.5 适配现有技能 | `src/skills/adapters/` | 适配 3 个现有技能 | pending |
| 4.6 编写测试 | `tests/unit/test_skills.py` | 所有测试通过 | pending |
| 4.7 发布 v0.4.0 | PyPI 包 | 可安装并运行 | pending |

### 验证方案

```bash
# 工作流引擎测试
python -m pytest tests/unit/test_workflow.py -v
uaek workflow --config ./tests/fixtures/workflow.yaml

# 技能加载器测试
python -m pytest tests/unit/test_skills.py -v
uaek skill list
uaek skill run verification-framework
```

### Phase 2 完成标准

- [ ] 工作流引擎支持 3 个并行任务
- [ ] 技能加载器加载 3 个现有技能
- [ ] 在 2 个 Agent 平台上运行
- [ ] 所有单元测试通过
- [ ] 文档完整

---

## Phase 3：记忆层（第 9-12 周）

### 目标

1. 上下文管理器 v1 — 自适应压缩 + 分层记忆
2. 跨会话记忆 v1 — 持久化 + 向量索引

### 任务清单

#### Week 9-10：上下文管理器

| 任务 | 产出 | 验证标准 | 状态 |
|------|------|----------|------|
| 5.1 设计记忆接口 | `src/memory/interface.py` | 接口定义完整 | pending |
| 5.2 实现分层记忆 | `src/memory/layers.py` | L1/L2/L3 三层正确 | pending |
| 5.3 实现压缩算法 | `src/memory/compression.py` | 压缩率 >60% | pending |
| 5.4 实现关键信息提取 | `src/memory/extraction.py` | 关键信息保留率 >90% | pending |
| 5.5 实现利用率监控 | `src/memory/monitor.py` | 实时监控正确 | pending |
| 5.6 编写测试 | `tests/unit/test_memory.py` | 所有测试通过 | pending |
| 5.7 发布 v0.5.0 | PyPI 包 | 可安装并运行 | pending |

#### Week 11-12：跨会话记忆

| 任务 | 产出 | 验证标准 | 状态 |
|------|------|----------|------|
| 6.1 实现持久化存储 | `src/memory/persistence.py` | 跨会话数据正确 | pending |
| 6.2 实现向量索引 | `src/memory/vector_index.py` | 语义搜索正确 | pending |
| 6.3 实现关键词索引 | `src/memory/keyword_index.py` | 精确匹配正确 | pending |
| 6.4 实现时间线索引 | `src/memory/timeline.py` | 时间排序正确 | pending |
| 6.5 实现记忆查询 | `src/memory/query.py` | 多种查询方式正确 | pending |
| 6.6 编写测试 | `tests/unit/test_persistence.py` | 所有测试通过 | pending |
| 6.7 发布 v0.6.0 | PyPI 包 | 可安装并运行 | pending |

### 验证方案

```bash
# 上下文管理器测试
python -m pytest tests/unit/test_memory.py -v
uaek memory add "Decision: keep workflow actions safe" --layer l3 --tag decision
uaek memory query "workflow actions" --layer l3
uaek memory compress --layer l3 --target-ratio 0.5

# 跨会话记忆测试
python -m pytest tests/unit/test_persistence.py -v
uaek memory restore
```

### Phase 3 完成标准

- [ ] 上下文管理器在 40%+ 利用率下保持性能
- [ ] 跨会话记忆在 3 个会话间保持一致性
- [ ] 在 3 个 Agent 平台上运行
- [ ] 所有单元测试通过
- [ ] 文档完整

---

## Phase 4：集成层（第 13-16 周）

### 目标

1. UAEK 集成 — 完整套件 + CLI
2. 基准测试 — 对比报告 + 优化

### 任务清单

#### Week 13-14：UAEK 集成

| 任务 | 产出 | 验证标准 | 状态 |
|------|------|----------|------|
| 7.1 设计统一接口 | `src/harness/interface.py` | 接口定义完整 | complete |
| 7.2 实现组件集成 | `src/harness/local.py` | effort/workflow/verify/memory/report 链路可运行 | partial |
| 7.3 实现 CLI | `src/cli.py` | `uaek run` 与核心 CLI 命令正确 | complete |
| 7.4 实现配置管理 | `src/config.py` | 配置加载正确 | complete |
| 7.5 实现日志系统 | `src/logger.py` | JSONL 日志输出正确 | complete |
| 7.6 编写集成测试 | `tests/integration/test_integration.py` | 所有测试通过 | complete |
| 7.7 发布 v1.0.0 | PyPI 包 | 可安装并运行 | pending |

#### Week 15-16：基准测试

| 任务 | 产出 | 验证标准 | 状态 |
|------|------|----------|------|
| 8.1 设计基准测试套件 | `src/benchmark.py` + `benchmarks/baselines/fable5.example.json` | quick suite 可生成 JSON 证据并读取 baseline metadata | partial |
| 8.2 实现 Fable 5 对标测试 | `benchmarks/fable5_comparison.py` | 对比结果正确 | pending |
| 8.3 实现跨平台测试 | `benchmarks/cross_platform.py` | 3 个平台结果一致 | pending |
| 8.4 实现成本对比测试 | `benchmarks/cost_comparison.py` | 成本降低 30%+ | pending |
| 8.5 生成对比报告 | `benchmarks/results/benchmark-quick.json` | 本地 quick score JSON 已生成 | partial |
| 8.6 优化性能 | `src/optimizations/` | 性能提升 20%+ | pending |
| 8.7 发布 v1.1.0 | PyPI 包 | 可安装并运行 | pending |

### 验证方案

```bash
# 集成测试
python -m pytest tests/integration/test_integration.py -v
uaek run "implement user authentication" --output /tmp/uaek-run.json
uaek run "implement user authentication" --config ./config/default.yaml --log-file /tmp/uaek-run.jsonl --output /tmp/uaek-run.json

# 基准测试
python -m pytest tests/benchmark/test_benchmark.py -v
uaek benchmark --suite quick --iterations 2 --output ./benchmarks/results/
uaek benchmark --suite quick --iterations 2 --baseline ./benchmarks/baselines/fable5.example.json --output ./benchmarks/results/

# CI 门禁
python -m ruff check src api mcp tests
python -m mypy src api mcp
python -m pytest
python -m pytest --cov=src --cov-report=term
python -m pytest --cov=src --cov=api --cov=mcp --cov-report=term-missing

# P4 后续目标：uaek benchmark --suite fable5 --baseline ./benchmarks/baselines/fable5.completed.json --output ./benchmarks/results/
```

### Phase 4 完成标准

- [ ] UAEK 在 3 个 Agent 平台上完整运行
- [ ] 在 5 个指标上持平或超越 Fable 5
- [ ] 成本降低 30%+
- [ ] 开源发布
- [ ] 所有测试通过
- [ ] 文档完整

---

## 进度更新流程

### 每日

1. 更新 `PROGRESS_TRACKER.md` 中的任务状态
2. 记录遇到的问题到 findings ledger
3. 更新 `VERIFICATION_SCORECARD.md` 中的分数

### 每周

1. 回顾本周完成的任务
2. 更新 Phase 完成度
3. 调整下周计划

### 每 Phase

1. 运行完整验证方案
2. 更新 `VERIFICATION_SCORECARD.md` 中的 Phase 分数
3. 决定是否进入下一 Phase

---

## 问题处理流程

### 发现问题

1. 记录到 findings ledger：
   ```bash
   python3 ~/.hermes/skills/universal-agent-workflow/scripts/agent_findings.py --root . add "问题描述" --severity high --evidence "具体证据"
   ```

2. 评估严重性：
   - low：记录后继续
   - medium：记录后继续，但需要在 Phase 结束前解决
   - high：必须立即解决
   - critical：停止工作，立即解决

### 解决问题

1. 修复问题
2. 验证修复
3. 更新 findings ledger：
   ```bash
   python3 ~/.hermes/skills/universal-agent-workflow/scripts/agent_findings.py --root . resolve F001 --evidence "修复证据"
   ```

### Phase 完成门控

```bash
# 检查是否有未解决的高危问题
python3 ~/.hermes/skills/universal-agent-workflow/scripts/agent_findings.py --root . gate

# 检查是否所有目标完成
python3 ~/.hermes/skills/universal-agent-workflow/scripts/agent_goals.py --root . gate
```

---

## 工具和依赖

### 必需

- Python 3.11+
- pytest
- uv (推荐) 或 pip

### 可选

- ChromaDB（向量索引）
- SQLite（持久化存储）
- GitHub CLI（发布）

### 安装

```bash
cd /Users/audrey/项目/fable-research
pip install -e ".[dev]"
```

---

## 参考资源

- [universal-agent-workflow 技能](~/.hermes/skills/universal-agent-workflow/)
- [Fable 5 系统提示词](system_prompts_leaks/)
- [Weakness Catalog](WEAKNESS_CATALOG.md)
- [Architecture Extraction](ARCHITECTURE-EXTRACTION.md)
- [Research Proposal](RESEARCH_PROPOSAL.md)
- [Gap Analysis](GAP_ANALYSIS.md)
