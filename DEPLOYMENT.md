# 🚀 ModelScope 创空间部署指南

本文档提供了在 ModelScope 魔搭社区上部署 MiniMax H3 视频生成创空间的详细步骤。

## 📋 部署前准备

### 账户要求
- ModelScope 社区账户
- 访问权限（部分资源需要申请）

### 资源要求
- **推荐**: AMD MI300X (192GB 显存)
- **最低**: 80GB 显存（会启用内存交换，速度下降）
- **存储**: 至少 100GB 可用空间（模型约 52GB）
- **网络**: 稳定的网络连接用于下载模型

### 文件准备
确保已完成以下准备：
1. 本地测试通过 `python app.py`
2. 执行 `bash scripts/setup_comfyui.sh` 获取 ComfyUI 源码
3. 验证目录结构完整

---

## 🎯 部署步骤

### 1. 创建创空间

1. 访问 [ModelScope 创空间](https://modelscope.cn/studios)
2. 点击右上角头像 → "创建创空间"
3. 填写基本信息:
   - **SDK 类型**: Gradio
   - **英文名称**: `MiniMax-H3-AMD` (或自定义)
   - **中文名称**: `MiniMax H3 视频生成 AMD版` (或自定义)
   - **可见性**: 根据需求选择公开或私有
   - **许可证**: 选择合适的许可证

### 2. 上传代码

#### 方法一: Git 推送（推荐）

```bash
# 1. 创建本地 Git 仓库
cd MiniMax-H3-AMD-Studio
git init

# 2. 添加所有文件（排除模型和缓存）
git add .
git commit -m "Initial commit: MiniMax H3 AMD Studio"

# 3. 添加远程仓库（替换为实际的仓库地址）
git remote add origin https://oauth2:<YOUR_TOKEN>@www.modelscope.cn/studios/<YOUR_USERNAME>/<SPACE_NAME>.git

# 4. 推送代码
git push -u origin main
```

#### 方法二: 网页上传

1. 在创空间页面点击 "上传文件"
2. 拖拽或选择以下文件和目录:
   - `app.py`
   - `requirements.txt`
   - `README.md`
   - `start.sh`
   - `.modelscope`
   - `.env.example`
   - `workflow/`
   - `scripts/`
   - `ComfyUI/` (如果已执行 setup_comfyui.sh)
   - `.gitignore`

### 3. 配置创空间

#### 资源选择
- **GPU**: 选择 `AMD MI300X` (推荐) 或其他可用 GPU
- **内存**: 至少 192GB (MI300X) 或根据 GPU 配置
- **磁盘**: 至少 100GB

#### 镜像选择
- **Python 版本**: 3.11+
- **框架**: 选择预装 PyTorch 的镜像
- **AMD 环境**: 如果使用 AMD GPU，选择 ROCm 版本镜像

#### 环境变量（可选）

在创空间设置中添加以下环境变量:

```bash
# 模型配置
MODELSCOPE_MODEL_REPO=Comfy-Org/MiniMax-H3

# 性能配置
GEN_TIMEOUT=7200  # 2小时超时
COMFY_PORT=8188

# 运行配置
SKIP_MODEL_DOWNLOAD=0  # 首次部署设为 0，之后可设为 1
PYTHONUNBUFFERED=1
```

### 4. 启动创空间

1. 点击 "启动" 或 "运行" 按钮
2. 等待环境初始化（首次需要安装依赖）
3. 观察启动日志，确保没有错误

---

## 📊 首次启动流程

首次启动时，应用会自动执行以下操作:

### 1. 环境检测
```
🔍 检测 GPU 类型...
🔍 检查磁盘空间...
🔍 验证 Python 版本...
```

### 2. ComfyUI 初始化
```
📁 检查 ComfyUI 源码...
🔄 如果不存在，从 GitHub 克隆...
🔧 应用 audio_scale 补丁...
```

### 3. 模型下载（约 52GB）
```
🚀 开始下载模型...
📥 下载扩散模型 (19.5GB)...
📥 下载文本编码器 (25.3GB)...
📥 下载视频 VAE (4.9GB)...
📥 下载音频 VAE (578MB)...
📥 下载 Turbo LoRA (1.9GB)...
✅ 模型下载完成
```

### 4. 服务启动
```
🎯 启动 ComfyUI 服务...
⏳ 等待服务就绪...
✅ 初始化完成，后端就绪
```

**预计总时间**: 30-60 分钟（取决于网络速度）

---

## 🧪 部署验证

### 1. 检查服务状态
在 Gradio 界面的状态栏应该显示:
```
🖥️  服务状态：✅ 后端就绪，可以生成
🎮 GPU类型：AMD ROCm（MI300X 调优已启用）
💾 显存状态：总计: 192.0GB, 已分配: 0.0GB, 已预留: 0.0GB, 可用: 192.0GB
📊 任务状态：💤 空闲
💿 磁盘: 50.0GB可用
🤖 模型: ✅ 完整
📦 模型仓库：Comfy-Org/MiniMax-H3
```

### 2. 测试生成功能
1. 点击任意示例提示词按钮
2. 选择分辨率 "864 x 480（快速预览）"
3. 设置时长为 2 秒
4. 启用 Turbo 模式
5. 点击 "🎬 生成视频"

### 3. 观察生成过程
- 状态栏应该显示任务运行状态
- 显存使用应该逐渐增加
- 生成完成后应该显示视频结果

---

## ⚙️ 高级配置

### 自定义模型

如需使用不同的模型，设置环境变量:

```bash
# NVIDIA GPU 用户
CLIP_NAME=qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors

# 自定义模型仓库
MODELSCOPE_MODEL_REPO=your-username/your-model-repo
```

### 性能调优

#### AMD MI300X 优化
应用会自动设置以下环境变量:
```bash
TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
PYTORCH_TUNABLEOP_ENABLED=1
HSA_OVERRIDE_GFX_VERSION=9.4.2
MIOPEN_FIND_MODE=FAST
```

#### NVIDIA GPU 优化
```bash
# CUDA 内存管理
PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# 禁用不必要的功能
TORCH_nn_CUDA_ENABLE_CUBLASLT=0
```

### 资源限制

#### 限制并发任务
在 `app.py` 中修改:
```python
demo.queue(concurrency_count=1)  # 只允许一个任务
```

#### 设置内存限制
```bash
# 限制 Python 内存使用
MALLOC_TRIM_THRESHOLD_=100000
```

---

## 🔄 更新和维护

### 更新代码

```bash
# 拉取最新代码
git pull origin main

# 重启创空间以应用更改
```

### 更新模型

```bash
# 设置环境变量重新下载
export SKIP_MODEL_DOWNLOAD=0

# 或手动删除模型文件后重启
rm -rf ComfyUI/models/*
```

### 清理缓存

```bash
# 清理输出文件
rm -rf outputs/*

# 清理日志文件
rm -rf logs/*.log.*

# 清理 GPU 缓存（在 Gradio 界面点击"清理GPU资源"按钮）
```

---

## 📈 监控和日志

### 查看日志

在创空间控制台查看实时日志，或下载日志文件:
- `logs/studio.log` - 主应用日志
- `logs/studio.log.1` - 历史日志（自动轮转）

### 性能监控

使用 Gradio 界面中的状态栏监控:
- GPU 显存使用情况
- 任务运行状态
- 磁盘空间
- 模型完整性

### 告警设置

建议设置以下告警:
- 磁盘空间不足（< 20GB）
- 服务异常重启
- 生成任务失败率过高

---

## 🛡️ 安全考虑

### 访问控制
- 设置创空间为私有（如果需要）
- 配置访问密码（如平台支持）
- 限制 API 调用频率

### 数据安全
- 定期备份重要配置
- 不要在代码中硬编码敏感信息
- 使用环境变量管理配置

### 内容审核
- 监控生成内容
- 设置内容过滤规则
- 遵守平台内容政策

---

## 🐛 常见部署问题

### 启动失败
**症状**: 创空间无法启动

**解决方案**:
1. 检查 `requirements.txt` 依赖是否完整
2. 确认 Python 版本兼容性
3. 查看启动日志中的错误信息
4. 验证文件权限

### 模型下载失败
**症状**: 模型下载过程中断或失败

**解决方案**:
1. 检查网络连接
2. 确认磁盘空间充足
3. 验证 ModelScope 服务状态
4. 手动下载模型文件

### GPU 识别失败
**症状**: 应用无法识别 GPU

**解决方案**:
1. 确认选择了正确的镜像类型
2. 检查 GPU 驱动是否正确安装
3. 验证 CUDA/ROCm 环境变量
4. 重启创空间

### 性能问题
**症状**: 生成速度慢或超时

**解决方案**:
1. 确认使用了正确的 GPU 类型
2. 检查显存使用情况
3. 降低生成分辨率或时长
4. 使用 Turbo 模式

---

## 📞 获取支持

如遇到部署问题:

1. **查看日志**: 检查 `logs/studio.log` 获取详细错误信息
2. **参考文档**: 阅读 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
3. **查看文章**: 参考 [配套文章](https://www.modelscope.cn/learn/436000)
4. **提交 Issue**: 在 ModelScope 社区提交问题，请包含:
   - 详细错误信息
   - 日志文件
   - 环境配置
   - 重现步骤

---

## 🎉 部署完成

部署成功后，您将拥有一个功能完整的 MiniMax H3 视频生成创空间，具有以下特性:

- ✅ 自动模型下载和管理
- ✅ 智能错误处理和恢复
- ✅ 多 GPU 类型支持（AMD/NVIDIA）
- ✅ 实时性能监控
- ✅ 用户友好的界面
- ✅ 完整的日志记录
- ✅ 自动故障恢复

开始享受高质量的视频生成体验吧！