---
name: effort-control
description: Effort 调度控制 - 根据任务复杂度调整工作深度
tags: [effort, optimization, cost, dispatch]
version: 1.0.0
---

# Effort 控制

## 核心原则

**根据任务复杂度调整工作深度，避免过度或不足。**

> "Don't run a $200 harness on a $9 task."

## Effort 级别

| 级别 | 适用场景 | 调度短语 | 验证深度 |
|------|----------|----------|----------|
| **LOW** | 简单任务 | "routine task, skip self-review" | 跳过验证 |
| **MEDIUM** | 标准任务 | "standard task, one self-check" | 一次自检 |
| **HIGH** | 复杂任务 | "complex task, full self-verification" | 完整自检 |
| **XHIGH** | 关键任务 | "critical task, fresh-context cross-verification" | 全新上下文交叉验证 |

## 复杂度指标

| 指标 | LOW | MEDIUM | HIGH | XHIGH |
|------|-----|--------|------|-------|
| 文件数 | 1-3 | 4-10 | 10+ | 20+ |
| 依赖深度 | 0 | 1-2 | 3-5 | 5+ |
| 模糊度 | 低 | 中 | 高 | 极高 |
| 可逆度 | 高 | 中 | 低 | 极低 |

## 使用方式

### 自动分类

```bash
# 自动分析任务复杂度
uaek effort --task "implement auth module"

# 输出
# Effort: high (confidence: 85%)
# Dispatch: complex task, full self-verification
# Verification: 完整自检
# Reasoning: 涉及多个文件，有复杂依赖
```

### 手动指定

```bash
# 手动指定 Effort 级别
uaek effort --task "deploy to production" --level xhigh

# 输出
# Effort: xhigh
# Dispatch: critical task, fresh-context cross-verification
# Verification: 全新上下文交叉验证
```

### 指定语言

```bash
# 中文调度短语
uaek effort --task "implement auth module" --language zh

# 输出
# Effort: high
# Dispatch: 这是一个复杂任务。充分推理，但信息齐全后立即行动。完成前进行完整的需求自检。
```

## 调度短语注入

根据 Effort 级别注入对应的调度短语到 Agent 的提示词中：

### LOW

```
This is a routine task. No over-deliberation, handle concisely. Skip self-review.
```

### MEDIUM

```
This is a standard task. Collect necessary context, don't exceed scope. One key requirement self-check before completion.
```

### HIGH

```
This is a complex task. Reason thoroughly, but act once information is complete. Full requirement self-check before completion.
```

### XHIGH

```
This is the highest sensitivity level. Review all edge cases, cross-reference every judgment with actual evidence from this session. Fresh-context cross-verification.
```

## 特殊规则

### 安全相关任务

如果任务涉及以下内容，强制使用 XHIGH：
- 数据库操作
- 生产环境部署
- 删除操作
- 安全相关代码

### 简单任务

如果任务满足以下条件，使用 LOW：
- 只涉及 1-2 个文件
- 没有复杂依赖
- 需求明确
- 可逆操作

## 成本控制

| Effort 级别 | 相对成本 | 适用场景 |
|------------|----------|----------|
| LOW | 1x | 快速修复、简单编辑 |
| MEDIUM | 2x | 标准功能开发 |
| HIGH | 4x | 复杂重构、多文件修改 |
| XHIGH | 8x | 关键操作、安全相关 |

## 示例

### 示例 1：简单任务

```bash
uaek effort --task "fix typo in README"
# Effort: low
# 理由：单文件，需求明确，可逆
```

### 示例 2：复杂任务

```bash
uaek effort --task "refactor authentication system with 10+ files"
# Effort: high
# 理由：多文件，复杂依赖，需求可能模糊
```

### 示例 3：关键任务

```bash
uaek effort --task "deploy to production database"
# Effort: xhigh
# 理由：不可逆操作，安全相关
```
