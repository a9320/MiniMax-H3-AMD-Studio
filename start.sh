#!/bin/bash
# ModelScope 创空间启动脚本
# 用于在创空间环境中正确初始化和启动应用

set -e

echo "🚀 启动 MiniMax H3 创空间..."

# 检查Python版本
echo "📋 检查Python环境..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python版本: $python_version"

# 检查必要的目录
echo "📁 检查目录结构..."
mkdir -p logs outputs

# 设置环境变量
export PYTHONUNBUFFERED=1
export GRADIO_SERVER_NAME="0.0.0.0"
export GRADIO_SERVER_PORT="${PORT:-7860}"
export GRADIO_SHARE="${GRADIO_SHARE:-false}"

# 显示配置信息
echo "⚙️  配置信息:"
echo "   - 服务器地址: $GRADIO_SERVER_NAME:$GRADIO_SERVER_PORT"
echo "   - 工作目录: $(pwd)"
echo "   - 模型仓库: ${MODELSCOPE_MODEL_REPO:-Comfy-Org/MiniMax-H3}"
echo "   - 跳过模型下载: ${SKIP_MODEL_DOWNLOAD:-0}"

# 检查磁盘空间
echo "💾 检查磁盘空间..."
df -h "$(pwd)" | tail -1 | awk '{print "   可用空间: " $4}'

# 启动应用
echo "🎯 启动Gradio应用..."
python3 app.py