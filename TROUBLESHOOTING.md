# 🔧 MiniMax H3 创空间故障排除指南

本指南提供了常见问题的解决方案和调试技巧。

## 📋 目录
1. [启动问题](#启动问题)
2. [模型下载问题](#模型下载问题)
3. [生成相关问题](#生成相关问题)
4. [性能问题](#性能问题)
5. [网络问题](#网络问题)
6. [ComfyUI 相关问题](#comfyui-相关问题)

---

## 🚀 启动问题

### 应用无法启动
**症状**: 创空间启动失败或一直处于初始化状态

**解决方案**:
1. 检查日志文件: `logs/studio.log`
2. 确认 Python 版本是否为 3.11+
3. 检查磁盘空间是否足够（至少 60GB）
4. 验证依赖是否正确安装: `pip install -r requirements.txt`

### ComfyUI 克隆失败
**症状**: 日志显示 "ComfyUI 源码缺失且自动克隆失败"

**解决方案**:
1. 检查网络连接，确保可以访问 GitHub
2. 手动执行: `bash scripts/setup_comfyui.sh`
3. 将 `ComfyUI/` 目录提交到创空间仓库
4. 如果 GitHub 访问受限，应用会自动尝试国内镜像源

---

## 📥 模型下载问题

### 模型下载失败
**症状**: 模型下载过程中报错或超时

**解决方案**:
1. 检查网络连接和 ModelScope 服务状态
2. 确认磁盘空间充足（需要约 52GB）
3. 如果中断，重新启动会自动断点续传
4. 手动下载: `bash scripts/download_models.sh`

### 模型文件完整性问题
**症状**: 生成时报错 "模型下载不完整"

**解决方案**:
1. 检查 `ComfyUI/models/` 目录结构
2. 验证以下文件是否存在:
   ```
   ComfyUI/models/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors
   ComfyUI/models/text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors
   ComfyUI/models/vae/minimax_h3_video_vae_fp16.safetensors
   ComfyUI/models/vae/minimax_h3_audio_vae_fp32.safetensors
   ComfyUI/models/loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors
   ```
3. 删除不完整的文件，重新启动应用

### 模型路径嵌套问题
**症状**: ComfyUI 找不到模型文件

**解决方案**:
1. 应用会自动修复嵌套路径问题
2. 检查是否有类似 `models/diffusion_models/diffusion_models/` 的嵌套目录
3. 手动整理: 将嵌套的文件移动到正确的位置

---

## 🎬 生成相关问题

### 只生成图片而不生成视频
**症状**: 输出是图片而不是视频

**原因**: 工作流配置错误，VAE 解码链配置不当

**解决方案**:
1. 不要手动修改 `app.py` 中的 `build_workflow()` 函数
2. 确保使用官方模板的双 VAE 解码链
3. 对照 `workflow/minimax_h3_t2v_api.json` 检查配置
4. 重启创空间，应用会使用内置的正确工作流

### audio_scale 属性错误
**症状**: 报错 `AttributeError: ... audio_scale`

**原因**: ComfyUI 版本兼容性问题

**解决方案**:
1. 应用启动时会自动修复此问题
2. 如果仍然出现，手动执行: `python scripts/fix_audio_scale.py`
3. 重启创空间

### 生成超时
**症状**: 生成过程长时间无响应或超时

**解决方案**:
1. 增加超时时间: 设置环境变量 `GEN_TIMEOUT=7200`（2小时）
2. 检查 GPU 状态和显存使用情况
3. 尝试降低分辨率或减少时长
4. 确认没有其他任务占用 GPU

---

## ⚡ 性能问题

### 生成速度慢
**症状**: 生成时间过长

**优化建议**:
1. 使用 Turbo 模式（8 步采样）
2. 从低分辨率开始测试（864x480）
3. 减少生成时长（从 2 秒开始）
4. 确保使用正确的 GPU（AMD MI300X 推荐使用 ROCm 版本）

### 显存不足（OOM）
**症状**: 报错 "out of memory" 或 "CUDA out of memory"

**解决方案**:
1. 降低分辨率: 选择 864x480 或 1024x576
2. 减少生成时长
3. 等待其他任务完成后再提交新任务
4. 如果是 NVIDIA GPU，考虑使用 `nvfp4_awq` 模型

### GPU 利用率低
**症状**: GPU 利用率不高，生成速度慢

**解决方案**:
1. 检查是否正确检测到 GPU 类型
2. AMD GPU 确认 ROCm 环境变量正确设置
3. NVIDIA GPU 确认 CUDA 版本兼容
4. 重启创空间以重新初始化 GPU

---

## 🌐 网络问题

### 无法连接到 ComfyUI 服务
**症状**: 报错 "连接被拒绝" 或 "Connection refused"

**解决方案**:
1. 检查 ComfyUI 进程是否正在运行
2. 确认端口 8188 没有被占用
3. 查看日志中的 ComfyUI 启动信息
4. 重启创空间

### ModelScope 下载失败
**症状**: 无法从 ModelScope 下载模型

**解决方案**:
1. 检查网络连接
2. 确认 ModelScope 服务状态
3. 尝试使用代理或镜像源
4. 手动下载模型文件并放置到正确位置

---

## 🔧 ComfyUI 相关问题

### ComfyUI 节点缺失
**症状**: 报错 "缺少节点类型"

**解决方案**:
1. 确保使用 ComfyUI 0.33.0 或更高版本
2. 检查自定义节点是否正确安装
3. 更新 ComfyUI: 重新执行 `scripts/setup_comfyui.sh`
4. 重启创空间

### ComfyUI 界面无法访问
**症状**: 无法打开 ComfyUI Web 界面

**注意**: 本创空间只暴露 Gradio 界面，不提供完整的 ComfyUI UI

**解决方案**:
1. 如需完整 ComfyUI 体验，请按文章在 DSW/Notebook 中部署
2. 本创空间专注于简化的文本到视频生成流程

---

## 📊 调试技巧

### 查看详细日志
```bash
# 实时查看日志
tail -f logs/studio.log

# 查看错误日志
grep ERROR logs/studio.log

# 查看最近的日志
tail -n 50 logs/studio.log
```

### 检查 GPU 状态
```bash
# AMD GPU
rocm-smi

# NVIDIA GPU
nvidia-smi
```

### 手动测试 ComfyUI
```bash
# 启动 ComfyUI
cd ComfyUI
bash ../scripts/start_comfyui.sh

# 测试连接
curl http://127.0.0.1:8188/system_stats
```

### 清理 GPU 资源
在 Gradio 界面中点击 "🧹 清理GPU资源" 按钮，或手动执行:
```python
import torch
torch.cuda.empty_cache()
import gc
gc.collect()
```

---

## 🆘 获取帮助

如果以上解决方案都无法解决您的问题:

1. **查看日志**: `logs/studio.log` 包含详细的错误信息
2. **检查状态栏**: Gradio 界面上的状态栏显示实时状态
3. **参考文章**: [配套文章](https://www.modelscope.cn/learn/436000)
4. **提交问题**: 在 ModelScope 社区提交 Issue，请包含:
   - 错误信息
   - 日志文件
   - 环境信息（GPU类型、Python版本等）
   - 重现步骤

---

## 📝 常见环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `MODELSCOPE_MODEL_REPO` | `Comfy-Org/MiniMax-H3` | 模型仓库地址 |
| `SKIP_MODEL_DOWNLOAD` | `0` | 是否跳过模型下载 |
| `GEN_TIMEOUT` | `3600` | 生成超时时间（秒） |
| `COMFY_PORT` | `8188` | ComfyUI 服务端口 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

---

## 🔒 安全提醒

- 不要在提示词中包含敏感信息
- 定期清理输出目录以节省磁盘空间
- 注意生成内容的版权和使用合规性
- 在生产环境中建议设置适当的访问控制