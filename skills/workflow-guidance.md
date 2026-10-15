---
name: workflow-guidance
description: 工作流指导 - 使用 DAG 和并行调度管理复杂任务
tags: [workflow, dag, parallel, orchestration]
version: 1.0.0
---

# 工作流指导

## 核心原则

**复杂任务应该分解为可管理的子任务，并按依赖关系调度执行。**

> "Weak planners hurt more than weak executors."

## 首节点约定：私脑预检（brain-first，2026-10-15）

凡工作流含**研究/调研/排障/创作/交付/执行/复用经验类**任务，DAG 的第一个节点必须是私脑预检：

```yaml
- id: brain-check
  run: bash ~/项目/private-brain/scripts/brain-check.sh <课题关键词>
  # rc=0 命中 → 后续节点先读 L1 决定复用/防重复；rc=1 无命中 → 正常开新调研
```

产出落盘前加对账节点：`brain-check <产出标题关键词>`（防重复轮子；commit 时 dup-check 闸再兜一道）。

守则源：~/项目/devkit/methodology/brain-first.md（完整挂载矩阵见该文件）。

## 工作流类型

| 类型 | 适用场景 | 特点 |
|------|----------|------|
| **顺序** | 有严格依赖的任务 | 按顺序执行，一个失败则停止 |
| **并行** | 独立的任务 | 同时执行，提高效率 |
| **条件** | 有分支的任务 | 根据条件选择执行路径 |
| **DAG** | 复杂依赖的任务 | 自动调度，最优执行 |

## 使用方式

### 定义工作流

```yaml
# workflow.yaml
workflow:
  id: "auth-module"
  type: "dag"
  tasks:
    - id: "design"
      name: "设计认证模块"
      func: "design_auth"
      
    - id: "implement"
      name: "实现认证模块"
      func: "implement_auth"
      dependencies: ["design"]
      
    - id: "test"
      name: "测试认证模块"
      func: "test_auth"
      dependencies: ["implement"]
      
    - id: "document"
      name: "编写文档"
      func: "write_docs"
      dependencies: ["implement"]
      
    - id: "deploy"
      name: "部署认证模块"
      func: "deploy_auth"
      dependencies: ["test", "document"]
```

### 执行工作流

```bash
# 执行工作流
uaek workflow --config workflow.yaml

# 并行执行（自动检测依赖）
uaek workflow --config workflow.yaml --parallel

# 顺序执行
uaek workflow --config workflow.yaml --sequential
```

### 查看状态

```bash
# 查看工作流状态
uaek workflow status --id auth-module

# 输出
# ✅ design: completed
# ✅ implement: completed
# ✅ test: completed
# ⏳ document: running
# ⏸️ deploy: blocked
```

## DAG 设计原则

### 1. 最小化依赖

```yaml
# ❌ 错误：不必要的依赖
- id: "test"
  dependencies: ["design", "implement"]

# ✅ 正确：只依赖必要任务
- id: "test"
  dependencies: ["implement"]
```

### 2. 并行化独立任务

```yaml
# ✅ 文档和测试可以并行
- id: "test"
  dependencies: ["implement"]

- id: "document"
  dependencies: ["implement"]
```

### 3. 避免循环依赖

```yaml
# ❌ 错误：循环依赖
- id: "a"
  dependencies: ["b"]
- id: "b"
  dependencies: ["a"]

# ✅ 正确：单向依赖
- id: "a"
  dependencies: []
- id: "b"
  dependencies: ["a"]
```

## 任务状态

| 状态 | 含义 | 后续行动 |
|------|------|----------|
| **PENDING** | 等待执行 | 等待依赖完成 |
| **RUNNING** | 正在执行 | 等待完成 |
| **COMPLETED** | 执行成功 | 继续后续任务 |
| **FAILED** | 执行失败 | 修复后重试或跳过 |
| **SKIPPED** | 跳过执行 | 依赖失败导致跳过 |
| **BLOCKED** | 被阻塞 | 等待外部条件 |

## 错误处理

### 快速失败

```bash
# 一个任务失败则停止整个工作流
uaek workflow --config workflow.yaml --fail-fast
```

### 继续执行

```bash
# 一个任务失败继续执行其他任务
uaek workflow --config workflow.yaml --no-fail-fast
```

### 重试策略

```yaml
# 定义重试策略
tasks:
  - id: "flaky-test"
    retry:
      max_attempts: 3
      delay: 5  # 秒
```

## 决策点：A/B 方案维度打分

当工作流遇到架构分叉（两种方案都可行），**不要直接选一个——先做维度打分再决策**。用户明确要求此流程。

1. **定义 A/B**：一句话各自的核心思路和改动点
2. **选维度**：3-6 个与决策相关的维度（路由精度、可维护性、实现成本等），标注权重
3. **打分**：每个维度 1-5 分，越高越好
4. **加权求和**：给出总分和推荐
5. **用户确认后才继续推进**

```markdown
| 维度 | 权重 | A | B | 说明 |
|------|:----:|:-:|:-:|------|
| 精度 | 25% | 3 | 5 | ... |
| 成本 | 10% | 5 | 2 | ... |
| **总分** | | **3.55** | **4.05** | |
```

**Pitfall**: skip the scoring and just pick one — the user will ask "为什么选这个" and you will have no quantitative basis. The scoring is the deliverable, not just the conclusion.

## 最佳实践

### 1. 任务粒度

- **太粗**：难以并行，难以调试
- **太细**：调度开销大，难以管理
- **合适**：5-15 分钟可完成的任务

### 2. 依赖声明

- 明确声明所有依赖
- 避免隐式依赖
- 最小化依赖范围

### 3. 错误处理

- 为每个任务定义错误处理策略
- 记录详细的错误信息
- 支持重试和回滚

### 4. 可观测性

- 记录每个任务的执行时间
- 记录每个任务的输入输出
- 支持任务级别的日志

## 示例

### 示例 1：功能开发

```yaml
workflow:
  id: "feature-auth"
  type: "dag"
  tasks:
    - id: "research"
      name: "调研认证方案"
      func: "research_auth"
      
    - id: "design"
      name: "设计认证模块"
      func: "design_auth"
      dependencies: ["research"]
      
    - id: "implement-backend"
      name: "实现后端认证"
      func: "implement_backend"
      dependencies: ["design"]
      
    - id: "implement-frontend"
      name: "实现前端认证"
      func: "implement_frontend"
      dependencies: ["design"]
      
    - id: "integrate"
      name: "集成测试"
      func: "integration_test"
      dependencies: ["implement-backend", "implement-frontend"]
      
    - id: "deploy"
      name: "部署"
      func: "deploy"
      dependencies: ["integrate"]
```

### 示例 2：代码重构

```yaml
workflow:
  id: "refactor-auth"
  type: "sequential"
  tasks:
    - id: "analyze"
      name: "分析现有代码"
      func: "analyze_code"
      
    - id: "plan"
      name: "制定重构计划"
      func: "plan_refactor"
      dependencies: ["analyze"]
      
    - id: "refactor"
      name: "执行重构"
      func: "execute_refactor"
      dependencies: ["plan"]
      
    - id: "test"
      name: "测试重构结果"
      func: "test_refactor"
      dependencies: ["refactor"]
      
    - id: "cleanup"
      name: "清理旧代码"
      func: "cleanup"
      dependencies: ["test"]
```
