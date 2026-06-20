# 🇺 UAEK — 通用 Agent 增强套件

![CI](https://github.com/Audrey-cn/universal-agent-embedding-kit/actions/workflows/ci.yml/badge.svg)

> 模型无关、可嵌入的 Agent 能力套件 —— 验证、上下文管理、Effort 调度、
> 记忆和工作流，外加一套诚实基准。

## 快速开始

```bash
git clone https://github.com/Audrey-cn/universal-agent-embedding-kit.git
cd universal-agent-embedding-kit
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
uaek --help
uaek benchmark --suite adversarial
python -m pytest -q
```

## 这是什么？

UAEK 始于对一个已退役前沿 Agent（代号 "Fable 5"）的研究，
核心发现：**Agent 的竞争力来自工程架构，而非模型本身**。

UAEK 把 Fable 5 的有效工程实践提取为可复用组件，
并对它的弱点逐个击破 —— 用诚实可验证的指标说话。

## 组件概览

| 组件 | 模块 | 作用 |
|------|------|------|
| 通用验证 | `src/verify`, `src/adversarial_verification.py` | 执行级、对抗性验证（不自评分数） |
| 自适应上下文 | `src/context_management.py` | 相关性过滤 + 压缩，对抗上下文腐烂 |
| Effort 调度 | `src/effort` | 分类任务 → 分配合理推理量 |
| 成本模型 | `src/cost_model.py` | Cache 感知的成本核算 |
| 真实场景基准 | `src/scenario_benchmark.py` | 多维评分，抓 pass/fail 漏掉的回归 |
| 跨平台能力矩阵 | `src/capability_matrix.py` | 驱动并客观评分真实 Agent 平台 |
| 工作流 / 记忆 / 技能 | `src/workflow`, `src/memory`, `src/skills` | 编排原语 |

## 核心方法论

**证据强度阶梯**：
1. 确定性本地基准 → 2. 压力/对抗测试 → 3. 真实数据 → 4. 实时测量 → 5. 外部验证

**红队硬化**：报告一个数字之前，先让独立 Agent 尝试证明它是虚高的，
然后加固到它扛得住攻击为止。数字不是在变高，而是在变可信。

## 诚实证据

| 维度 | 结果 | 诚实注记 |
|------|------|----------|
| 自评分作弊率 | naive ~60-71% → 对抗 0% | 限于此语料+生成器 |
| 上下文利用率 | 自适应 0.85 @70% 利用率 | 非自适应优势的 live 证明 |
| 成本降低 | 建模 -49%；实时 warm 会话 -82% | TTL 条件性 |
| 真实场景基准 | 多维评分抓回归 | 框架+种子集 |
| 跨平台矩阵 | 4/4 平台通过客观评分 | 一个 CLI 路由共享模型 |

## 输出方式

- **CLI**: `uaek verify / effort / workflow / memory / benchmark / capability ...`
- **HTTP API**: `api/server.py`
- **MCP 服务器**: `mcp/server.py`

## 详细安装

### 前置要求

- Python 3.11+
- 可选: ChromaDB（向量记忆）

### 一键安装

```bash
bash scripts/setup.sh
```

### 手动安装

```bash
git clone https://github.com/Audrey-cn/universal-agent-embedding-kit.git
cd universal-agent-embedding-kit
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
ruff check src api mcp tests
mypy src api mcp
python -m pytest
uaek --help
```

## 已知局限

- 基准是确定性本地模型 + 实时抽检
- 无直接 Fable 5 baseline（参考模型已退役）
- 模型后端 ≤3 互异

## 许可证

MIT — 见 [LICENSE](LICENSE)。

[English README](README.md) | [CHANGELOG](CHANGELOG.md)
