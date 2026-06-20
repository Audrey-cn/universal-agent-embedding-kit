#!/usr/bin/env bash
set -euo pipefail

# ==============================================================
# UAEK — Universal Agent Embedding Kit 一键安装脚本
# ==============================================================
# 用法: bash scripts/setup.sh
# 作用: 创建虚拟环境、安装依赖、运行质量门禁

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "========================================"
echo " UAEK — Universal Agent Embedding Kit"
echo " 一键安装"
echo "========================================"
echo ""

# 检查 Python
PYTHON=""
for cmd in python3.11 python3.12 python3; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "❌ 未找到 Python 3.11+。请先安装 Python。"
    exit 1
fi

echo "✅ Python: $($PYTHON --version)"

# 创建虚拟环境
if [ ! -d .venv ]; then
    echo "🔧 创建虚拟环境..."
    $PYTHON -m venv .venv
else
    echo "✅ 虚拟环境已存在 (.venv)"
fi

# 激活
source .venv/bin/activate

# 升级 pip
echo "🔧 升级 pip..."
pip install --upgrade pip --quiet

# 安装依赖
echo "📦 安装 UAEK 开发依赖..."
pip install -e ".[dev]" --quiet

echo ""
echo "========================================"
echo " ✅ 安装完成"
echo "========================================"
echo ""
echo "可用命令:"
echo "  uaek --help              — 查看 CLI 帮助"
echo "  uaek benchmark --suite quick  — 跑快速基准"
echo "  python -m pytest -q      — 跑测试 (nq)"
echo ""
echo "快速入门:"
echo "  source .venv/bin/activate"
echo "  uaek benchmark --suite adversarial"
echo ""

# 可选: 运行质量门禁
if [[ "${1:-}" == "--verify" || "${1:-}" == "-v" ]]; then
    echo "========================================"
    echo " 🔍 运行质量门禁"
    echo "========================================"
    echo ""
    echo "--- ruff ---"
    python -m ruff check src api mcp tests && echo "✅ ruff passed" || echo "⚠️  ruff 有警告"
    echo ""
    echo "--- mypy ---"
    python -m mypy src api mcp && echo "✅ mypy passed" || echo "⚠️  mypy 有警告"
    echo ""
    echo "--- pytest ---"
    python -m pytest -q && echo "✅ 所有测试通过" || echo "❌ 测试有失败"
fi
