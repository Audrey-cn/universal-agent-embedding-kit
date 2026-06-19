---
name: verification-framework
description: 通用验证框架 - 在完成任务前必须执行验证
tags: [verification, quality, testing]
version: 1.0.0
---

# 验证框架

## 核心原则

**在声称任务完成之前，必须执行验证。**

> "만든 쪽의 컨텍스트를 물려받은 검증자는 같은 맹점을 공유한다"
> （A verifier that inherited the maker's context shares the same blind spots）

## 验证流程

### 1. 确定验证类型

| 产出物类型 | 验证方式 |
|-----------|----------|
| 代码 | 运行测试 + lint + 构建 |
| 文档 | 检查格式 + 链接 + 拼写 |
| 配置 | 验证语法 + 语义 |
| UI | 渲染 + 观察 + 交互测试 |
| 数据 | 完整性 + 格式 + 样本验证 |

### 2. 执行验证

```bash
# 自动检测验证类型
uaek verify --artifact <产出物路径>

# 指定验证类型
uaek verify --artifact <产出物路径> --type test
uaek verify --artifact <产出物路径> --type build
uaek verify --artifact <产出物路径> --type lint

# 指定验收标准
uaek verify --artifact <产出物路径> --criteria <验收标准路径>
```

### 3. 检查结果

| 结果 | 含义 | 后续行动 |
|------|------|----------|
| ✅ PASS | 验证通过 | 可以声称完成 |
| ❌ FAIL | 验证失败 | 必须修复后重新验证 |
| ⚠️ INDETERMINATE | 无法判断 | 必须明确说明原因 |

## 全新上下文验证

**关键原则**：验证者不继承执行者的上下文。

```bash
# 在全新上下文中验证
uaek verify --artifact <产出物路径> --fresh-context
```

**为什么重要**：
- 执行者的错误会被执行者的推理所掩盖
- 全新上下文可以发现执行者忽略的问题
- 避免"看起来正确"但实际有 bug 的情况

## 验证标准清单

每个任务必须有明确的验收标准：

- [ ] 功能正确性：是否按需求工作？
- [ ] 代码质量：是否符合编码规范？
- [ ] 测试覆盖率：是否有足够的测试？
- [ ] 文档完整性：是否有必要的文档？
- [ ] 边界情况：是否处理了异常情况？
- [ ] 安全性：是否有安全漏洞？

## 禁止行为

- ❌ 声称完成但未验证
- ❌ 忽略验证失败
- ❌ 跳过验证步骤
- ❌ 使用"看起来正确"作为验证结果
- ❌ 验证者继承执行者的上下文

## 示例

### 示例 1：验证 Python 代码

```bash
# 运行测试
uaek verify --artifact ./src/auth.py --type test

# 运行 lint
uaek verify --artifact ./src/auth.py --type lint

# 运行构建
uaek verify --artifact ./ --type build
```

### 示例 2：验证文档

```bash
# 检查 Markdown 格式
uaek verify --artifact ./docs/README.md --type lint

# 检查链接
uaek verify --artifact ./docs/ --type link-check
```

### 示例 3：全新上下文验证

```bash
# 在全新上下文中验证
uaek verify --artifact ./output/ --criteria ./spec.md --fresh-context
```
