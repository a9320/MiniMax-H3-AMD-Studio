---
title: MiniMax H3 视频生成（AMD MI300X 适配版）
emoji: 🎬
colorFrom: red
colorTo: purple
sdk: gradio
app_file: app.py
pinned: false
license: apache-2.0
tags:
  - comfyui
  - video
  - minimax
  - amd
---

# MiniMax H3 视频生成创空间（AMD MI300X / ROCm 适配版）

基于 **ComfyUI + 官方 MiniMax H3 模板** 的文生视频应用，生成带**原生立体声**的 MP4。
本仓库是配套文章
[《192GB 显存真香警告：魔搭 AMD MI300X 部署 ComfyUI + MiniMax H3 的血泪实录》](https://www.modelscope.cn/learn/436000)
的一键部署版本，文章中的每个坑在这里都有对应的自动化处理。

## 功能特性

- 纯 Gradio 界面：输入提示词 → 生成带声音的视频，无需接触 ComfyUI 节点
- 自动下载 AMD INT8 convrot 版模型（DiT 19.5G + 文本编码器 25.3G + 双 VAE + Turbo LoRA，共约 52G）
- 启动时自动修复 ComfyUI 0.33.0 的 `audio_scale` 属性缺失问题（文章坑 2，幂等补丁）
- 自动归位 `modelscope download` 造成的嵌套路径（文章坑 1）
- 始终使用官方模板的视频/音频双 VAE 解码链，杜绝维度不匹配（文章坑 3）
- 检测到 AMD ROCm GPU 时自动注入 MI300X 调优环境变量（文章第五节）
- 单任务限流，适配创空间共享 GPU

## 项目结构

```
├── app.py                      # 创空间入口：Gradio 界面 + ComfyUI 子进程管理 + 官方模板 API 工作流
├── requirements.txt            # 依赖（已注释 torch，防止覆盖镜像预装版本）
├── workflow/
│   ├── minimax_h3_t2v_api.json # 由官方模板 video_minimax_h3_t2v.json 转换的 API 工作流（参考用，app.py 内置等价构建器）
│   └── README.md               # 工作流来源与自定义说明
├── scripts/
│   ├── setup_comfyui.sh        # 一次性：克隆 ComfyUI 并清理 .git，之后提交进本仓库
│   ├── download_models.sh      # 独立模型下载脚本（含正确的 --local-dir 用法与校验）
│   ├── fix_audio_scale.py      # 独立补丁工具（app.py 启动时已自动执行）
│   └── start_comfyui.sh        # DSW/Notebook 环境手动启动 ComfyUI 用（ROCm 自动检测）
└── outputs/                    # 生成的视频缓存目录
```

## 部署步骤（创空间）

1. **创建创空间**：魔搭社区 → 头像 → 创建创空间
   - SDK 类型：**Gradio**
   - 英文名称：如 `MiniMax-H3-AMD`
2. **准备代码**（二选一）：
   - Git：`git clone https://oauth2:<TOKEN>@www.modelscope.cn/studios/<用户名>/<空间名>.git`，把本仓库内容复制进去并推送；
   - 网页：直接上传本仓库文件（若 ComfyUI 目录已随仓库分发则无需额外操作）。
3. **集成 ComfyUI 源码**（推荐，避免运行环境访问 GitHub 失败——文章坑 4）：

   ```bash
   bash scripts/setup_comfyui.sh   # 克隆 ComfyUI 并删除 .git
   ```

   然后把 `ComfyUI/` 目录一起提交推送（体积约几十 MB，不含模型）。
   若跳过此步，`app.py` 会在启动时尝试自动浅克隆，失败会给出明确报错。

4. **选择资源**：模型共约 52G 且需常驻显存，推荐 **AMD MI300X（192G，文章同款）**；
   80G 显存可跑（部分模块会卸载到内存，速度下降）；48G 及以下不建议（会 OOM）。
   xGPU 资源需先申请加入「xGPU Playground」组织。

5. **选择镜像**：与资源匹配即可（Python 3.11 + 预装 PyTorch 的魔搭官方镜像）。
   若在 AMD 资源上运行，请选 ROCm 版镜像，`app.py` 会自动识别并启用 MI300X 调优参数。

6. **部署并等待**：首次启动会自动下载约 52G 模型（魔搭源，支持断点续传），日志出现
   `初始化完成，后端就绪` 即可使用。模型下载完成后会保留在磁盘，重启无需重复下载
   （前提是创空间实例磁盘持久化，具体以平台策略为准）。

## 环境变量（可选）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `MODELSCOPE_MODEL_REPO` | `Comfy-Org/MiniMax-H3` | 模型仓库 |
| `CLIP_NAME` | `qwen3vl_32b_minimax_h3_int8_convrot.safetensors` | AMD 版文本编码器；NVIDIA 24G 卡可改为 `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` |
| `UNET_NAME` / `VIDEO_VAE_NAME` / `AUDIO_VAE_NAME` / `LORA_NAME` | 见 app.py | 模型文件名覆盖 |
| `SKIP_MODEL_DOWNLOAD` | `0` | 设为 `1` 跳过下载（模型已备好时） |
| `GEN_TIMEOUT` | `3600` | 单次生成超时秒数 |

## 文章踩坑点 ↔ 本仓库处理对照

| 文章中的坑 | 本仓库的处理 |
|---|---|
| 坑 1：模型下载路径嵌套 | `app.py` 下载后自动校验，发现嵌套自动 `mv` 归位 |
| 坑 2：`audio_scale` 属性失踪 | 启动时自动给 `comfy/model_sampling.py` 打补丁（幂等），也有独立脚本 `scripts/fix_audio_scale.py` |
| 坑 3：VAE 解码维度不匹配 | 工作流固定为官方模板的视频/音频双解码链，用户不可改节点 |
| 坑 4：DSW 网络封锁 | ComfyUI 源码随仓库分发，运行期不依赖 GitHub |
| 坑 5：实例重启依赖丢失 | 所有依赖在 `requirements.txt` 声明，构建期安装 |
| 坑 6：时长改不动 | 界面直接暴露「时长（秒）」，帧数按官方公式 `max(5, round(d*24)) + (5 - (x % 17)) % 17` 自动换算 |
| 性能调优 | ROCm 下自动设置 `PYTORCH_TUNABLEOP_ENABLED` / `HSA_OVERRIDE_GFX_VERSION=9.4.2` 等 |

## 常见问题

**Q：生成的是图片而不是视频？**
本应用的工作流写死在 `app.py` 的 `build_workflow()` 中，与官方模板解码链一致，正常不会出图片。
如果你 fork 后改了它，请对照 `workflow/minimax_h3_t2v_api.json` 恢复。

**Q：报 `AttributeError: ... audio_scale`？**
说明 ComfyUI 版本较旧且补丁未生效。重启创空间（补丁在启动时自动执行），
或进入容器手动执行 `python scripts/fix_audio_scale.py`。

**Q：显存不足（OOM）？**
按文章 FAQ：确认用的是 INT8 convrot 模型（默认就是）、不要在他人任务运行时提交、
不要同时开多个生成任务。若 GPU 显存 < 80G，建议换 `nvfp4_awq` 文本编码器。

**Q：想看完整 ComfyUI 界面？**
本创空间只暴露 Gradio 界面。完整 ComfyUI UI 请按文章在 DSW/Notebook 中部署体验。

## 本地调试

```bash
pip install -r requirements.txt
bash scripts/setup_comfyui.sh
python app.py   # 打开 http://localhost:7860
```

## 许可证与声明

模型权重遵循 MiniMax 相关许可；生成内容请注意合规使用。
本项目基于魔搭社区真实部署经验整理，转载请注明出处。
