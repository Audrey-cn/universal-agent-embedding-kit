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
# 先确认当前安装支持的参数，再按位置参数传入产出物路径
uaek verify --help
uaek verify <产出物路径>

# 指定验证类型（当前 CLI: test/build/lint/render/diff/adversarial）
uaek verify <产出物路径> --type test
uaek verify <产出物路径> --type build
uaek verify <产出物路径> --type lint

# 指定验收标准
uaek verify <产出物路径> --criteria <验收标准路径>
```

不要使用 `--artifact` 或 `--fresh-context`，除非当前版本的 `uaek verify --help` 明确列出这些选项；路径参数是位置参数，CLI 版本也可能有差异。独立复核应通过新建验证上下文/独立审阅者实现，而不是假设命令行有未公开的开关。

### 3. 检查结果

| 结果 | 含义 | 后续行动 |
|------|------|----------|
| ✅ PASS | 验证通过 | 可以声称完成 |
| ❌ FAIL | 验证失败 | 必须修复后重新验证 |
| ⚠️ INDETERMINATE | 无法判断 | 必须明确说明原因 |

**独立复核**：先用 `uaek verify --help` 确认此版本是否提供全新上下文选项；若没有，就使用单独的审阅者/验证会话，不要拼接未支持的 CLI flags。

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
# 先按仓库文档运行测试/语法检查；具体命令以项目工作流为准
uaek verify ./src/auth.py --type test
uaek verify ./src/auth.py --type lint
uaek verify . --type build
```

### 示例 2：验证文档

```bash
uaek verify ./docs/README.md --type lint
```

### 示例 3：指定验收标准

```bash
uaek verify ./output/ --criteria ./spec.md
```

如果 CLI 报 unsupported file type，应改用该产物类型的原生校验（例如 JSON 用解析器、代码用项目测试和 lint），并如实记录验证范围；不要把验证器不支持误报为产物本身失败。
