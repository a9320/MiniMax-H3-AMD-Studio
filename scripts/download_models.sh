#!/bin/bash
# 文章 3.3 节：MiniMax H3 AMD 版模型下载（魔搭源，速度远快于 HuggingFace）
# ⚠️ 关键（文章坑1）：--local-dir 统一指向 models，
#    工具会按仓库相对路径自动创建子目录；
#    若写成 --local-dir models/diffusion_models 会导致路径嵌套，ComfyUI 找不到模型。
set -e
cd "$(dirname "$0")/.."
COMFY_DIR=${1:-ComfyUI}
[ -d "$COMFY_DIR" ] || { echo "未找到 $COMFY_DIR，请先运行 scripts/setup_comfyui.sh"; exit 1; }
cd "$COMFY_DIR"
mkdir -p models/diffusion_models models/text_encoders models/vae models/loras

modelscope download --model Comfy-Org/MiniMax-H3 \
    diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors --local-dir models
modelscope download --model Comfy-Org/MiniMax-H3 \
    text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors --local-dir models
modelscope download --model Comfy-Org/MiniMax-H3 \
    vae/minimax_h3_video_vae_fp16.safetensors vae/minimax_h3_audio_vae_fp32.safetensors --local-dir models
modelscope download --model Comfy-Org/MiniMax-H3 \
    loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors --local-dir models

echo "========== 模型文件完整性检查 =========="
ls -lh models/diffusion_models/ models/text_encoders/ models/vae/ models/loras/
du -sh models/
