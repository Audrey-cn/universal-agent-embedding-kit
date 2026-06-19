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
