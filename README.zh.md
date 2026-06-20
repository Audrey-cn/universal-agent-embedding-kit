<div align="center">

<img src="docs/banner.svg" alt="UAEK — Universal Agent Embedding Kit" width="100%">

<br/>

**模型无关、可嵌入的 Agent 增强套件 —— 为任意 Agent 平台补上更强的验证、上下文管理、Effort 调度、记忆与工作流;配套一套基准,只守一条规矩:报告扛得住攻击的数字,而不是好看的数字。**

<br/>

[![CI](https://github.com/Audrey-cn/universal-agent-embedding-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/Audrey-cn/universal-agent-embedding-kit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Version](https://img.shields.io/badge/version-0.1.0--alpha-orange.svg)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-389%20passing-brightgreen.svg)](#状态)
[![Ruff](https://img.shields.io/badge/lint-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[快速开始](#-快速开始) · [诚实证据](#-诚实证据) · [方法论](#-方法论才是核心) · [路线图](#-路线图) · [贡献](CONTRIBUTING.md) · [English](README.md)

</div>

---

## 为什么是 UAEK

UAEK 始于对一个已退役前沿 Agent(代号 "Fable 5")的研究,核心论点:**它的竞争力来自工程架构,而非模型本身**。UAEK 把那套工程 —— 验证、自适应上下文、Effort 调度、记忆、工作流 —— 提取为可嵌入*任意* Agent 运行时的一层,并对每一项主张做诚实测量,包括那些"测出来没我们想的好"的地方。

它真正的差异不是某个数字,而是一套**纪律**:每个头条指标都经过红队攻击,并按"证据强度阶梯"标注所在的档位,把注意事项摊在明面上。

## 🚀 快速开始

> 需要 **Python 3.11+**。从源码安装(暂未发布到 PyPI)。

**一行搞定(clone + 虚拟环境 + 安装 + 门禁):**

```bash
git clone https://github.com/Audrey-cn/universal-agent-embedding-kit.git
cd universal-agent-embedding-kit
bash scripts/setup.sh          # 创建 .venv、安装依赖、跑 ruff + mypy + 测试
```

**或手动安装:**

```bash
git clone https://github.com/Audrey-cn/universal-agent-embedding-kit.git
cd universal-agent-embedding-kit
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

**试一下:**

```bash
uaek --help
uaek benchmark --suite adversarial   # 自评分作弊率证据
uaek capability matrix               # 跨平台真实任务评分矩阵
uaek audit --output -                # 完整审计报告(JSON 输出到 stdout)
python -m pytest -q                  # 389 个测试
```

## 🧩 组件概览

| 组件 | 模块 | 作用 |
|------|------|------|
| 🛡️ 通用验证 | `src/verify`, `src/adversarial_verification.py` | 执行级、**对抗性**验证(不自评分数) |
| 🧠 自适应上下文 | `src/context_management.py` | 相关性过滤 + 压缩,对抗上下文腐烂 |
| 🎚️ Effort 调度 | `src/effort` | 分类任务 → 分配合理推理量 |
| 💰 成本模型 | `src/cost_model.py` | Cache 感知的成本核算 |
| 🎯 真实场景基准 | `src/scenario_benchmark.py` | 多维评分,抓 pass/fail 漏掉的回归 |
| 🔌 跨平台能力矩阵 | `src/capability_matrix.py` | 驱动并客观评分真实 Agent 平台 |
| 🔧 工作流 / 记忆 / 技能 / Harness | `src/workflow`, `src/memory`, `src/skills`, `src/harness` | 编排原语 |

三种暴露方式:**CLI**(`uaek`)、**HTTP API**(`api/`)、**MCP 服务器**(`mcp/`)。

## 🔬 诚实证据

下表每个数字都经过一轮**红队**(独立 Agent 试图证明它虚高)再**加固**到扛得住的值。这个过程里数字是*往下走*的 —— 这正是重点。每项都标注了它在证据阶梯上的档位。

| 维度 | 结果 | 档位 | 诚实注记 |
|------|------|:----:|----------|
| 自评分作弊率 | naive ~60–71% → **对抗 0%**(目标 <10%) | ③ | 限于此语料 + 生成器,**不是**不可能性证明 |
| 上下文利用率 | 自适应 **0.85** 期望准确率 @70% 利用率 vs naive 0.57 | ③ | live needle 测试 31K tokens 召回 6/6 —— 验证的是检索,不是自适应优势的 live 证明 |
| 成本降低 | 建模 −43%(1h 档 −49%);**实时 warm 会话 −82%,命中 92%** | ④ | TTL 条件性;全冷会话反而比 baseline 更贵 |
| 真实场景基准 | 多维评分;能标出"功能齐全但**有回归**"的解 | ③ | 30 场景 / 28 类别 —— 还不是 100+ live 多小时会话 |
| 跨平台矩阵 | **4/4** 平台通过客观评分的 live 代码任务 | ④ | 一个 CLI 路由到共享后端,衡量的是平台可嵌入性,而非 4 个模型 |

<a id="状态"></a>**门禁:** 389 测试通过 · ruff + mypy 全绿 · CI 绿。完整拆解与出处见 [`VERIFICATION_SCORECARD.md`](VERIFICATION_SCORECARD.md)。

## 🪜 方法论才是核心

这里最可复用的不是某个指标,而是两条实践强制的纪律:

- **证据强度阶梯** —— ① 本地基准 → ② 压力/对抗 → ③ 真实数据 → ④ 实时测量 → ⑤ 外部验证。"提升"一个指标意味着**往阶梯上爬**,**而不是去拧旋钮**。
- **红队硬化** —— 报告一个自测数字前,先派独立 Agent *证明它虚高*,再加固到它扛得住为止。

详见 [`docs/methodology.md`](docs/methodology.md)、研究框架 [`RESEARCH_PROPOSAL.md`](RESEARCH_PROPOSAL.md),以及操作手册 [`SOP.md`](SOP.md) / [`EXECUTION_MANUAL.md`](EXECUTION_MANUAL.md)。

## 🗺️ 路线图

往证据阶梯上爬,就是路线图:

- [ ] **档位 ④ → ⑤** —— 多 provider / 多采样 live 运行;超出单账户的远端 CI 证据
- [ ] **真实场景语料** —— 从 30 个确定性场景扩到 100+ live 多小时会话
- [ ] **成本·冷路径** —— 测 TTL-miss 为主的真实会话,而不只是 warm 会话
- [ ] **外部基线** —— 为已退役参考模型找一个可复现的替代基线
- [x] **红队硬化轮** —— 每个头条指标都被攻击并加固
- [x] **已发布、CI 门禁、证据归档**的版本

## 🤝 贡献

欢迎 PR 和 issue —— 见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。唯一不可破的规矩:任何新增或改动的指标,都必须带上它的**档位**和**诚实注记**。提 PR 前请跑 `bash scripts/setup.sh`(或 `ruff check . && mypy src && pytest`)。安全问题报告见 [`SECURITY.md`](SECURITY.md)。

## ⚠️ 已知局限(请务必读)

- 基准是**确定性本地模型 + 实时抽检**,不是大规模 live 评测。凡是建模得出的结论都已注明。
- 实时测量主要依赖单一 provider;多 provider 扩展与**外部(档位 ⑤)验证仍是未完成工作**。
- 原始参考模型已退役,因此**没有直接基线**;对比使用公开记录数字 + proxy 验证,绝不伪造重跑。

## 📄 许可证

[MIT](LICENSE) · [Changelog](CHANGELOG.md) · [English README](README.md)
