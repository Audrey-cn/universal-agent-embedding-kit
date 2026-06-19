---
name: agent-enhancement
description: Agent 增强套件 - 综合使用验证、Effort、工作流和记忆管理
tags: [agent, enhancement, orchestration, quality]
version: 1.0.0
---

# Agent 增强套件

## 核心理念

**通过四个维度增强 Agent 的能力：验证、Effort、工作流、记忆。**

> "Fable 5 的秘密不是模型，是工程。"

## 四大组件

| 组件 | 作用 | 文件 |
|------|------|------|
| **验证框架** | 确保产出物质量 | `verification-framework.md` |
| **Effort 控制** | 优化资源分配 | `effort-control.md` |
| **工作流指导** | 管理复杂任务 | `workflow-guidance.md` |
| **记忆管理** | 管理长期上下文 | `memory-management.md` |

## 综合使用流程

### 1. 任务分析

```bash
# 分析任务复杂度
uaek effort --task "实现用户认证模块"

# 输出
# Effort: high
# 建议：使用 DAG 工作流，分阶段执行
```

### 2. 工作流定义

```yaml
# 根据 Effort 分析结果定义工作流
workflow:
  id: "auth-module"
  type: "dag"
  tasks:
    - id: "research"
      name: "调研认证方案"
      effort: "medium"
      
    - id: "design"
      name: "设计认证架构"
      effort: "high"
      dependencies: ["research"]
      
    - id: "implement"
      name: "实现认证模块"
      effort: "high"
      dependencies: ["design"]
      
    - id: "test"
      name: "测试认证模块"
      effort: "medium"
      dependencies: ["implement"]
      
    - id: "document"
      name: "编写文档"
      effort: "low"
      dependencies: ["implement"]
```

### 3. 记忆管理

```bash
# 记录架构决策
uaek memory add --layer l3 \
  --content "决定使用 JWT + OAuth2 认证方案" \
  --importance 0.95 \
  --tags "decision,authentication"

# 记录技术约束
uaek memory add --layer l3 \
  --content "必须支持多因素认证" \
  --importance 0.9 \
  --tags "constraint,authentication"
```

### 4. 验证执行

```bash
# 每个任务完成后验证
uaek verify --artifact ./src/auth.py --type test
uaek verify --artifact ./src/auth.py --type lint
uaek verify --artifact ./docs/auth.md --type lint
```

## 超越 Fable 5 的维度

### 维度 1：平台兼容性

| 平台 | Fable 5 | UAEK |
|------|---------|------|
| Claude Code | ✅ | ✅ |
| Cursor | ❌ | ✅ |
| GPT-5.5 | ❌ | ✅ |
| Gemini | ❌ | ✅ |
| 开源模型 | ❌ | ✅ |

### 维度 2：自评分作弊率

| 指标 | Fable 5 | UAEK 目标 |
|------|---------|-----------|
| 作弊率 | 47-74% | <10% |
| 方法 | 自我批评 | 全新上下文验证 |

### 维度 3：上下文利用率

| 指标 | Fable 5 | UAEK 目标 |
|------|---------|-----------|
| 利用率上限 | ~40% | ~70% |
| 方法 | 压缩 | 分层记忆 + 智能压缩 |

### 维度 4：成本控制

| 指标 | Fable 5 | UAEK 目标 |
|------|---------|-----------|
| 成本 | Opus 的 2 倍 | 降低 30-50% |
| 方法 | Effort 分级 | 预测性调度 |

## 使用示例

### 示例 1：完整功能开发

```bash
# 1. 分析任务
uaek effort --task "实现用户认证模块"

# 2. 记录决策
uaek memory add --layer l3 --content "决定使用 JWT 认证" --importance 0.95

# 3. 执行工作流
uaek workflow --config auth-workflow.yaml

# 4. 验证每个任务
uaek verify --artifact ./src/auth.py --type test
uaek verify --artifact ./docs/auth.md --type lint

# 5. 持久化记忆
uaek memory persist
```

### 示例 2：代码重构

```bash
# 1. 分析任务
uaek effort --task "重构认证系统，涉及 10+ 文件"

# 2. 记录约束
uaek memory add --layer l2 --content "必须保持向后兼容" --importance 0.9

# 3. 执行工作流
uaek workflow --config refactor-workflow.yaml

# 4. 全新上下文验证
uaek verify --artifact ./ --type test --fresh-context

# 5. 压缩记忆
uaek memory compress
```

### 示例 3：紧急修复

```bash
# 1. 分析任务（自动检测为 LOW）
uaek effort --task "修复 README 中的拼写错误"

# 2. 快速执行
# 跳过工作流，直接修复

# 3. 简单验证
uaek verify --artifact ./README.md --type lint

# 4. 记录修复
uaek memory add --layer l1 --content "修复了 README 中的拼写错误" --importance 0.3
```

## 最佳实践

### 1. 根据任务选择组件

| 任务类型 | 验证 | Effort | 工作流 | 记忆 |
|----------|------|--------|--------|------|
| 简单修复 | ✅ | LOW | ❌ | L1 |
| 标准开发 | ✅ | MEDIUM | ✅ | L2 |
| 复杂重构 | ✅ | HIGH | ✅ | L2+L3 |
| 关键操作 | ✅ | XHIGH | ✅ | L3 |

### 2. 定期维护

- 每天：压缩 L1 和 L2
- 每周：压缩 L3，清理过期记忆
- 每月：审查重要性阈值，调整压缩策略

### 3. 持续改进

- 记录每个任务的 Effort 分类准确率
- 记录每个验证的通过率
- 记录每个工作流的执行时间
- 根据数据调整参数

## 与 Fable 5 的对比

| 维度 | Fable 5 | UAEK |
|------|---------|------|
| **平台** | 仅 Claude Code | 任意 Agent |
| **验证** | 自我批评 | 全新上下文验证 |
| **Effort** | 提示词注入 | 智能分类 + 调度短语 |
| **工作流** | 内置 | 可配置 DAG |
| **记忆** | 8 模块 | 分层 + 压缩 + 持久化 |
| **成本** | 高 | 可控 |
| **透明度** | 黑盒 | 白盒 |

## 总结

UAEK 通过四个维度增强 Agent 的能力：

1. **验证**：确保产出物质量，避免"看起来正确"
2. **Effort**：优化资源分配，避免过度或不足
3. **工作流**：管理复杂任务，提高执行效率
4. **记忆**：管理长期上下文，保持一致性

**目标**：在多个维度超越 Fable 5，同时保持平台无关性和透明度。
