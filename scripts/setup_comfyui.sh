#!/bin/bash
# 一次性初始化：把 ComfyUI 源码纳入本仓库（对应文章坑4：运行环境访问 GitHub 不可靠）
# 固定到文章实测的 v0.33.0，保证与创空间行为一致（audio_scale 补丁即为此版本准备）
# 用法：bash scripts/setup_comfyui.sh  之后把 ComfyUI/ 目录 git add 并推送
set -e
cd "$(dirname "$0")/.."
if [ -f ComfyUI/main.py ]; then
    echo "ComfyUI 已存在，跳过克隆"
else
    # 优先走加速镜像（国内网络直连 GitHub 不稳定），失败再回落官方源
    git clone --depth 1 --branch v0.33.0 "https://gh-proxy.com/https://github.com/Comfy-Org/ComfyUI.git" \
        || git clone --depth 1 --branch v0.33.0 https://github.com/Comfy-Org/ComfyUI.git
fi
rm -rf ComfyUI/.git
echo "完成。请将 ComfyUI/ 目录提交进创空间仓库（不要提交 models/）。"
