# UAEK 开发 SOP

> 标准操作流程
> 确保完全隔离，不影响主机环境

---

## 一、环境隔离原则

### 1.1 虚拟环境

- **所有开发必须在虚拟环境中进行**
- 虚拟环境路径：`/Users/audrey/项目/fable-research/.venv`
- **禁止**在系统 Python 或全局环境中安装任何依赖
- **禁止**修改主机的 `.hermes/`、`.claude/` 或其他配置

### 1.2 依赖管理

- 使用 `uv` 管理依赖（推荐）或 `pip`
- 所有依赖锁定在 `requirements.txt` 或 `pyproject.toml`
- **禁止**使用 `sudo pip install` 或全局安装

### 1.3 测试隔离

- 测试在虚拟环境中运行
- 测试数据使用临时目录（`tempfile`）
- **禁止**测试修改主机文件系统

---

## 二、开发流程

### 2.1 开始开发

```bash
# 1. 进入项目目录
cd /Users/audrey/项目/fable-research

# 2. 激活虚拟环境
source .venv/bin/activate

# 3. 确认环境
python --version  # 应显示 3.11+
which python      # 应指向 .venv/bin/python

# 4. 安装依赖（如果尚未安装）
pip install -e ".[dev]"

# 5. 开始开发
```

### 2.2 编写代码

1. **遵循现有代码风格**
   - 使用 type hints
   - 编写 docstring
   - 保持函数简洁（<50 行）

2. **每个模块必须有对应测试**
   - 测试文件：`tests/unit/test_<module>.py`
   - 测试类：`Test<ClassName>`
   - 测试方法：`test_<description>`

3. **提交前检查**
   ```bash
   # 运行测试
   python -m pytest tests/ -v

   # 运行 linter
   python -m ruff check src/

   # 运行类型检查
   python -m mypy src/
   ```

### 2.3 提交代码

```bash
# 1. 确认所有测试通过
python -m pytest tests/ -v

# 2. 更新进度追踪器
# 编辑 PROGRESS_TRACKER.md，更新任务状态

# 3. 提交
git add .
git commit -m "feat: <描述>"
```

---

## 三、测试流程

### 3.1 单元测试

```bash
# 运行所有单元测试
python -m pytest tests/unit/ -v

# 运行特定测试文件
python -m pytest tests/unit/test_verify.py -v

# 运行特定测试类
python -m pytest tests/unit/test_verify.py::TestVerificationResult -v

# 运行特定测试方法
python -m pytest tests/unit/test_verify.py::TestVerificationResult::test_pass_result -v

# 显示覆盖率
python -m pytest tests/unit/ -v --cov=src --cov-report=term-missing
```

### 3.2 集成测试

```bash
# 运行所有集成测试
python -m pytest tests/integration/ -v

# 运行特定集成测试
python -m pytest tests/integration/test_integration.py -v
```

### 3.3 基准测试

```bash
# 运行基准测试
python -m pytest tests/benchmark/ -v

# 生成报告
python -m pytest tests/benchmark/ -v --benchmark-json=benchmarks/results.json
```

### 3.4 测试覆盖率目标

| 模块 | 目标覆盖率 | 当前覆盖率 |
|------|-----------|-----------|
| src/verify/ | >80% | — |
| src/effort/ | >80% | — |
| src/workflow/ | >80% | — |
| src/memory/ | >80% | — |
| src/skills/ | >80% | — |
| src/harness/ | >80% | — |

---

## 四、验证流程

### 4.1 Phase 验证

每个 Phase 完成后，必须通过以下验证：

```bash
# 1. 运行所有测试
python -m pytest tests/ -v

# 2. 运行 linter
python -m ruff check src/

# 3. 运行类型检查
python -m mypy src/

# 4. 运行 CLI 验证
python -m src.cli verify ./tests/fixtures/simple_function.py
python -m src.cli effort "implement auth module"

# 5. 检查覆盖率
python -m pytest tests/ -v --cov=src --cov-report=term-missing
```

### 4.2 验证标准

| 验证项 | 标准 | 阻断级别 |
|--------|------|----------|
| 测试通过率 | 100% | critical |
| 代码覆盖率 | >80% | high |
| Linter 错误 | 0 | high |
| 类型检查错误 | 0 | medium |
| CLI 可运行 | 是 | critical |

### 4.3 验证失败处理

1. **Critical 失败**：停止工作，立即修复
2. **High 失败**：记录到 findings ledger，Phase 结束前修复
3. **Medium 失败**：记录到 findings ledger，可延后修复
4. **Low 失败**：记录到 findings ledger，可选修复

---

## 五、进度更新流程

### 5.1 每日更新

```bash
# 1. 更新 PROGRESS_TRACKER.md
# - 标记完成的任务
# - 记录遇到的问题
# - 更新每周日志

# 2. 更新 VERIFICATION_SCORECARD.md
# - 更新分数
# - 记录验证结果
```

### 5.2 每周回顾

1. 回顾本周完成的任务
2. 更新 Phase 完成度
3. 调整下周计划
4. 更新 `PROGRESS_TRACKER.md` 中的每周日志

### 5.3 Phase 完成

1. 运行完整验证流程
2. 更新 `VERIFICATION_SCORECARD.md` 中的 Phase 分数
3. 确认分数 ≥ 20/25
4. 确认无 high/critical 未解决 findings
5. 决定是否进入下一 Phase

---

## 六、问题处理流程

### 6.1 发现问题

```bash
# 记录到 findings ledger
python3 ~/.hermes/skills/universal-agent-workflow/scripts/agent_findings.py \
  --root . add "问题描述" --severity high --evidence "具体证据"
```

### 6.2 评估严重性

| 严重性 | 处理方式 |
|--------|----------|
| critical | 停止工作，立即解决 |
| high | 立即解决，或 Phase 结束前解决 |
| medium | 记录后继续，Phase 结束前解决 |
| low | 记录后继续，可选解决 |

### 6.3 解决问题

```bash
# 1. 修复问题

# 2. 验证修复
python -m pytest tests/ -v

# 3. 更新 findings ledger
python3 ~/.hermes/skills/universal-agent-workflow/scripts/agent_findings.py \
  --root . resolve F001 --evidence "修复证据"
```

---

## 七、代码风格

### 7.1 Python 风格

- 遵循 PEP 8
- 使用 type hints
- 编写 docstring（Google 风格）
- 函数长度 <50 行
- 类长度 <500 行

### 7.2 命名规范

- 类名：`PascalCase`
- 函数名：`snake_case`
- 变量名：`snake_case`
- 常量名：`UPPER_SNAKE_CASE`
- 文件名：`snake_case.py`

### 7.3 导入顺序

```python
# 1. 标准库
import os
import sys
from pathlib import Path

# 2. 第三方库
import pytest
from rich.console import Console

# 3. 本地模块
from src.verify import verify
from src.effort import classify
```

---

## 八、Git 工作流

### 8.1 分支策略

- `main`：稳定版本
- `develop`：开发分支
- `feature/<name>`：功能分支
- `fix/<name>`：修复分支

### 8.2 提交规范

```
<type>: <description>

类型：
- feat: 新功能
- fix: 修复
- docs: 文档
- style: 代码风格
- refactor: 重构
- test: 测试
- chore: 构建/工具
```

### 8.3 提交示例

```bash
git commit -m "feat: 实现验证框架接口"
git commit -m "fix: 修复测试运行器超时问题"
git commit -m "docs: 更新执行手册"
```

---

## 九、文档规范

### 9.1 代码文档

- 每个模块必须有模块级 docstring
- 每个类必须有类级 docstring
- 每个公共方法必须有方法级 docstring
- 复杂逻辑必须有行内注释

### 9.2 项目文档

- `README.md`：项目概述
- `EXECUTION_MANUAL.md`：执行手册
- `VERIFICATION_SCORECARD.md`：验证评分卡
- `PROGRESS_TRACKER.md`：进度追踪器
- `docs/architecture/`：架构文档
- `docs/api/`：API 文档
- `docs/guides/`：使用指南

### 9.3 文档更新

- 代码变更时同步更新文档
- Phase 完成时更新所有文档
- 重大变更时更新 README.md

---

## 十、安全规范

### 10.1 环境隔离

- 所有开发在虚拟环境中进行
- 禁止修改主机配置
- 禁止访问主机敏感数据

### 10.2 依赖安全

- 定期更新依赖
- 检查已知漏洞
- 避免使用未维护的依赖

### 10.3 代码安全

- 不硬编码密钥或密码
- 使用环境变量存储敏感配置
- 输入验证和错误处理

---

## 附录：常用命令

```bash
# 环境设置
cd /Users/audrey/项目/fable-research
source .venv/bin/activate
pip install -e ".[dev]"

# 运行测试
python -m pytest tests/ -v
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v
python -m pytest tests/benchmark/ -v

# 代码检查
python -m ruff check src/
python -m mypy src/

# CLI 使用
python -m src.cli verify <artifact>
python -m src.cli effort <task>
python -m src.cli workflow
python -m src.cli skill <name>
python -m src.cli benchmark

# 进度更新
python3 ~/.hermes/skills/universal-agent-workflow/scripts/agent_goals.py --root . list
python3 ~/.hermes/skills/universal-agent-workflow/scripts/agent_findings.py --root . list
```
