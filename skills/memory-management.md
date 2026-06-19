---
name: memory-management
description: 记忆管理 - 使用分层记忆系统管理长期上下文
tags: [memory, context, persistence, compression]
version: 1.0.0
---

# 记忆管理

## 核心原则

**上下文是有限的资源，必须智能管理。**

> "Context rot past ~40% utilization — performance falls as the window fills."

## 记忆层次

| 层次 | 名称 | 用途 | 生命周期 |
|------|------|------|----------|
| **L1** | 当前对话 | 当前对话的上下文 | 会话结束时清除 |
| **L2** | 当前任务 | 当前任务的上下文 | 任务完成时清除 |
| **L3** | 持久化记忆 | 跨会话的知识 | 永久保存 |

## 使用方式

### 添加记忆

```bash
# 添加到 L1（当前对话）
uaek memory add --layer l1 --content "用户想要实现认证模块"

# 添加到 L2（当前任务）
uaek memory add --layer l2 --content "决定使用 JWT 认证" --importance 0.9

# 添加到 L3（持久化记忆）
uaek memory add --layer l3 --content "项目使用 Python 3.11" --importance 0.8
```

### 查询记忆

```bash
# 按关键词查询
uaek memory query --keyword "认证"

# 按标签查询
uaek memory query --tags "decision,architecture"

# 按重要性查询
uaek memory query --min-importance 0.8

# 查询特定层
uaek memory query --layer l3 --keyword "Python"
```

### 压缩记忆

```bash
# 压缩所有层
uaek memory compress

# 压缩特定层
uaek memory compress --layer l1 --target-ratio 0.5

# 输出
# L1: 100 → 50 条 (压缩率 50%)
# L2: 200 → 120 条 (压缩率 40%)
# L3: 500 → 450 条 (压缩率 10%)
```

### 持久化记忆

```bash
# 保存到磁盘
uaek memory persist

# 从磁盘恢复
uaek memory restore

# 清除所有记忆
uaek memory clear
```

## 记忆条目结构

```json
{
  "id": "mem_001",
  "content": "决定使用 JWT 认证",
  "layer": "l2",
  "importance": 0.9,
  "timestamp": 1624000000.0,
  "tags": ["decision", "authentication"],
  "metadata": {
    "source": "architecture-review",
    "confidence": 0.95
  }
}
```

## 重要性计算

| 因素 | 权重 | 说明 |
|------|------|------|
| 决策 | +0.2 | "决定"、"选择"、"确定" |
| 约束 | +0.1 | "必须"、"限制"、"约束" |
| 错误 | +0.15 | "错误"、"失败"、"bug" |
| 需求 | +0.1 | "需求"、"规格"、"功能" |
| 标签 | +0.1 | 特定标签（如 "decision"） |

## 压缩策略

### L1 压缩

- **策略**：保留高重要性条目
- **阈值**：超过 50% 时触发
- **目标**：压缩到 50%

### L2 压缩

- **策略**：合并相似条目，移除重复
- **阈值**：超过 50% 时触发
- **目标**：压缩到 50%

### L3 压缩

- **策略**：保留高重要性条目
- **阈值**：超过 80% 时触发
- **目标**：压缩到 80%

## 利用率监控

```bash
# 查看利用率
uaek memory utilization

# 输出
# L1: 45/100 (45%) ⚠️ 接近阈值
# L2: 120/500 (24%) ✅ 正常
# L3: 2300/5000 (46%) ✅ 正常

# 设置阈值
uaek memory set-threshold --layer l1 --threshold 0.4
```

## 最佳实践

### 1. 记忆分类

- **决策**：标记为 "decision"，高重要性
- **约束**：标记为 "constraint"，高重要性
- **错误**：标记为 "error"，高重要性
- **日志**：低重要性，定期压缩

### 2. 定期压缩

- 每 10 次交互压缩一次 L1
- 每个任务结束压缩一次 L2
- 每天压缩一次 L3

### 3. 避免污染

- 不要将临时数据存入 L3
- 不要将重复数据存入多个层
- 不要将低质量数据存入高重要性层

### 4. 查询优化

- 使用标签缩小查询范围
- 使用重要性过滤低质量结果
- 使用时间范围限制历史数据

## 示例

### 示例 1：项目初始化

```bash
# 添加项目基本信息到 L3
uaek memory add --layer l3 --content "项目使用 Python 3.11" --importance 0.8 --tags "tech-stack"
uaek memory add --layer l3 --content "项目使用 FastAPI 框架" --importance 0.8 --tags "tech-stack"
uaek memory add --layer l3 --content "项目使用 PostgreSQL 数据库" --importance 0.8 --tags "tech-stack"
```

### 示例 2：架构决策

```bash
# 记录架构决策到 L3
uaek memory add --layer l3 \
  --content "决定使用微服务架构，因为需要独立部署和扩展" \
  --importance 0.95 \
  --tags "decision,architecture"
```

### 示例 3：错误记录

```bash
# 记录错误到 L2
uaek memory add --layer l2 \
  --content "JWT token 过期时间设置为 24 小时导致用户频繁登录" \
  --importance 0.9 \
  --tags "error,authentication"
```

### 示例 4：查询历史决策

```bash
# 查询所有架构决策
uaek memory query --tags "decision,architecture" --layer l3

# 输出
# [0.95] 决定使用微服务架构，因为需要独立部署和扩展
# [0.90] 决定使用 JWT 认证，因为无状态且易于扩展
# [0.85] 决定使用 PostgreSQL，因为需要复杂查询支持
```
