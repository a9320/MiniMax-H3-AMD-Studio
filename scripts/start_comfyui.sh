#!/bin/bash
# 在魔搭 DSW/Notebook 中手动启动 ComfyUI（文章 3.5 / 第五节）
# 创空间内不需要本脚本（由 app.py 托管），仅供 Notebook 调试用
set -e
cd "$(dirname "$0")/.."
COMFY_DIR=${1:-ComfyUI}
cd "$COMFY_DIR"

# 自动检测 ROCm 并注入 MI300X 调优环境变量（文章第五节）
if python3 -c "import torch,sys; sys.exit(0 if getattr(torch.version,'hip',None) else 1)" 2>/dev/null; then
    echo "检测到 AMD ROCm GPU，启用 MI300X 调优参数"
    export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
    export PYTORCH_TUNABLEOP_ENABLED=1
    export HSA_OVERRIDE_GFX_VERSION=9.4.2
    export MIOPEN_FIND_MODE=FAST
else
    echo "未检测到 ROCm，按默认 CUDA/CPU 环境启动"
fi

python main.py --port 8188 --listen 127.0.0.1 \
    --enable-cors-header --enable-compress-response-body --cache-none
