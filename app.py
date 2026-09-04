# -*- coding: utf-8 -*-
"""
MiniMax H3 视频生成创空间（AMD MI300X / ROCm 适配版）
=========================================================
配套文章：《192GB 显存真香警告：魔搭 AMD MI300X 部署 ComfyUI + MiniMax H3 的血泪实录》
https://www.modelscope.cn/learn/436000

本应用基于官方 ComfyUI 模板 video_minimax_h3_t2v.json 转换出的 API 工作流，
并按照文章经验做了以下自动化处理：
  坑1 模型下载路径嵌套   -> 下载后自动校验并在嵌套时自动归位
  坑2 audio_scale 缺失   -> 启动时自动为 comfy/model_sampling.py 打最小补丁
  坑3 VAE 维度不匹配     -> 始终使用官方模板的视频/音频双解码链，绝不手写工作流
  坑5 依赖丢失           -> 依赖全部由 requirements.txt 声明，启动时自检
  ROCm 优化             -> 检测到 AMD GPU 时自动注入 MI300X 调优环境变量
"""

import os
import re
import json
import time
import glob
import shutil
import random
import threading
import subprocess
import gc
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from functools import wraps

import requests
import gradio as gr

# ---------------------------------------------------------------- 配置 ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COMFY_DIR = os.path.join(BASE_DIR, "ComfyUI")
MODELS_DIR = os.path.join(COMFY_DIR, "models")
COMFY_HOST = "127.0.0.1"
COMFY_PORT = int(os.environ.get("COMFY_PORT", "8188"))
COMFY_URL = f"http://{COMFY_HOST}:{COMFY_PORT}"
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 模型仓库与文件名均可通过环境变量覆盖（见 README）
MODEL_REPO = os.environ.get("MODELSCOPE_MODEL_REPO", "Comfy-Org/MiniMax-H3")
UNET_NAME = os.environ.get("UNET_NAME", "minimax_h3_fl2va_pruned_int8_convrot.safetensors")
CLIP_NAME = os.environ.get("CLIP_NAME", "qwen3vl_32b_minimax_h3_int8_convrot.safetensors")
VIDEO_VAE_NAME = os.environ.get("VIDEO_VAE_NAME", "minimax_h3_video_vae_fp16.safetensors")
AUDIO_VAE_NAME = os.environ.get("AUDIO_VAE_NAME", "minimax_h3_audio_vae_fp32.safetensors")
LORA_NAME = os.environ.get("LORA_NAME", "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors")

SKIP_MODEL_DOWNLOAD = os.environ.get("SKIP_MODEL_DOWNLOAD", "0") == "1"
GEN_TIMEOUT = int(os.environ.get("GEN_TIMEOUT", "3600"))

# 期望的模型文件 -> 相对 models/ 的路径（文章 3.3 节的文件清单）
EXPECTED_MODELS = {
    f"diffusion_models/{UNET_NAME}": "扩散模型 DiT 主干 (~19.5G)",
    f"text_encoders/{CLIP_NAME}": "文本/视觉编码器 (~25.3G)",
    f"vae/{VIDEO_VAE_NAME}": "视频 VAE (~4.9G)",
    f"vae/{AUDIO_VAE_NAME}": "音频 VAE (~578M)",
    f"loras/{LORA_NAME}": "Turbo LoRA (~1.9G)",
}

# 示例提示词
EXAMPLE_PROMPTS = [
    (
        "🐱 橘猫追毛线球",
        "一只橘白相间的猫咪在阳光下的草地上追一颗红色毛线球，毛茸茸的尾巴高高翘起。\n\n"
        "画面：写实风格，浅景深，午后暖色调。\n"
        "镜头：低角度跟拍，猫咪扑向毛线球时镜头轻微推进。\n"
        "音频：鸟鸣、风吹草地的沙沙声、猫咪轻快的脚步声，轻快的原声吉他背景乐。\n\n"
        "画面中不要出现字幕、水印或文字。"
    ),
    (
        "👘 古风女子弹古琴",
        "一位穿着传统汉服的女子在古色古香的庭院中弹古琴，微风吹动她的长发和衣角。\n\n"
        "画面：水墨画风格，留白构图，月色朦胧。\n"
        "镜头：中景缓慢推进，细节特写古琴和手指。\n"
        "音频：古琴声、远处虫鸣、风吹竹叶声，空灵的背景音乐。\n\n"
        "画面中不要出现字幕、水印或文字。"
    ),
    (
        "🏙️ 赛博朋克飞车",
        "一辆未来感十足的飞车在霓虹灯闪烁的赛博朋克城市中穿梭，夜雨朦胧。\n\n"
        "画面：赛博朋克美学，体积光照明，雨滴效果，高对比度色彩。\n"
        "镜头：低角度跟拍，动态镜头运动，镜头雨滴效果。\n"
        "音频：引擎轰鸣声、城市环境音、合成波背景音乐。\n\n"
        "画面中不要出现字幕、水印或文字。"
    ),
    (
        "🌊 海边日出",
        "清晨的海边，太阳缓缓从海平面升起，金色的阳光洒在波浪上。\n\n"
        "画面：温暖的自然光色彩，动态的海浪纹理，飞鸟剪影。\n"
        "镜头：广角固定镜头，太阳升起过程的时间流逝。\n"
        "音频：海浪声、海鸥叫声、轻柔的海风声，宁静的自然音效。\n\n"
        "画面中不要出现字幕、水印或文字。"
    )
]

# 示例提示词描述
EXAMPLE_DESCRIPTIONS = {
    "🐱 橘猫追毛线球": "写实风格，猫咪动态，自然环境音",
    "👘 古风女子弹古琴": "水墨风格，古典美学，空灵音乐",
    "🏙️ 赛博朋克飞车": "科幻风格，动态镜头，电子音乐",
    "🌊 海边日出": "自然风光，时间流逝，宁静氛围"
}

RESOLUTION_PRESETS = {
    "864 x 480（快速预览，推荐先试）": (864, 480),
    "1024 x 576（质量确认）": (1024, 576),
    "1344 x 768（最终成片，H3 原生画布）": (1344, 768),
}

STATE = {"phase": "init", "detail": "应用启动中……", "comfy_ready": False, "proc": None}
GEN_LOCK = threading.Lock()


# ============================================================ 日志系统 ----
def setup_logging():
    """配置完善的日志系统，支持文件轮转和多级别日志。"""
    log_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)

    # 创建日志器
    logger = logging.getLogger("MiniMaxH3Studio")
    logger.setLevel(logging.INFO)

    # 避免重复添加处理器
    if logger.handlers:
        logger.handlers.clear()

    # 文件处理器（带轮转，每个文件最大10MB，保留5个备份）
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "studio.log"),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# 初始化日志系统
studio_logger = setup_logging()


def log(msg: str, level="info"):
    """统一的日志接口，同时更新状态和日志系统。"""
    log_func = getattr(studio_logger, level.lower(), studio_logger.info)
    log_func(msg)
    STATE["detail"] = msg
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ============================================================ 输入验证和安全 ----
def validate_prompt(prompt: str) -> str:
    """验证和清理用户输入的提示词，防止恶意输入。"""
    if not prompt or not prompt.strip():
        raise ValueError("提示词不能为空")

    original_length = len(prompt)
    if original_length > 5000:  # 限制提示词长度
        raise ValueError(f"提示词过长（{original_length}字符），请控制在5000字符以内")

    # 移除潜在的恶意内容（基本的XSS防护）
    dangerous_patterns = [
        r'<script.*?>.*?</script>',  # Script标签
        r'javascript:',  # JavaScript协议
        r'on\w+\s*=',  # 事件处理器如onclick=, onerror=
        r'data:text/html',  # Data URL
        r'vbscript:',  # VBScript协议
    ]

    cleaned_prompt = prompt
    for pattern in dangerous_patterns:
        if re.search(pattern, cleaned_prompt, re.IGNORECASE):
            matches = re.findall(pattern, cleaned_prompt, re.IGNORECASE)
            for match in matches:
                cleaned_prompt = cleaned_prompt.replace(match, '')
            log(f"检测到潜在危险内容并已清理: {pattern}", "warning")

    # 如果清理后内容为空，抛出错误
    if not cleaned_prompt.strip():
        raise ValueError("提示词包含不允许的内容，已被过滤")

    cleaned_length = len(cleaned_prompt)
    if cleaned_length != original_length:
        log(f"提示词已清理：从{original_length}字符减少到{cleaned_length}字符", "info")

    return cleaned_prompt.strip()


def safe_path_join(base, *paths):
    """安全的路径拼接，防止路径遍历攻击。"""
    try:
        full_path = os.path.abspath(os.path.join(base, *paths))
        base_path = os.path.abspath(base)

        if not full_path.startswith(base_path):
            raise ValueError("非法的文件路径：试图访问基础目录之外的文件")

        return full_path
    except Exception as e:
        raise ValueError(f"路径验证失败: {e}")


def validate_duration(duration: float) -> float:
    """验证生成时长参数。"""
    try:
        duration_float = float(duration)
        if duration_float < 0.5:
            raise ValueError("时长不能少于0.5秒")
        if duration_float > 15:  # 限制最大时长
            raise ValueError("时长不能超过15秒")
        return duration_float
    except (ValueError, TypeError) as e:
        raise ValueError(f"时长参数无效: {e}")


def validate_resolution(resolution: str) -> tuple:
    """验证分辨率参数。"""
    if resolution not in RESOLUTION_PRESETS:
        available = ", ".join(RESOLUTION_PRESETS.keys())
        raise ValueError(f"无效的分辨率选项。可用选项：{available}")
    return RESOLUTION_PRESETS[resolution]


def check_disk_space(required_gb=60):
    """检查磁盘空间是否足够。"""
    try:
        total, used, free = shutil.disk_usage(BASE_DIR)
        free_gb = free / (1024**3)

        if free_gb < required_gb:
            raise RuntimeError(
                f"磁盘空间不足：需要约{required_gb}GB（含模型文件），当前可用{free_gb:.1f}GB。"
                f"请清理磁盘空间或联系管理员。"
            )

        log(f"磁盘空间检查通过：可用 {free_gb:.1f}GB")
        return True
    except Exception as e:
        log(f"磁盘空间检查失败: {e}", "warning")
        return False  # 不因为检查失败而阻止启动


# ============================================================ 性能跟踪装饰器 ----
def track_performance(func):
    """性能跟踪装饰器，用于记录函数执行时间。"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        func_name = func.__name__
        try:
            log(f"⏱️ 开始执行: {func_name}", "debug")
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            log(f"✅ {func_name} 完成，耗时: {elapsed:.2f}秒", "debug")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            log(f"❌ {func_name} 失败 (耗时{elapsed:.2f}秒): {e}", "error")
            raise
    return wrapper


# ============================================================ 自定义错误类 ----
class StudioError(Exception):
    """自定义错误基类，支持用户友好消息和技术详情。"""
    def __init__(self, message, user_friendly=None, technical=None):
        self.message = message
        self.user_friendly = user_friendly or message
        self.technical = technical or message
        super().__init__(self.message)


class ModelNotFoundError(StudioError):
    """模型文件未找到错误。"""
    def __init__(self, model_name):
        super().__init__(
            f"模型文件未找到: {model_name}",
            f"所需的模型 {model_name} 未找到，请检查模型下载是否完成或重新启动创空间",
            f"Model file not found: {model_name}"
        )


class GPUInsufficientError(StudioError):
    """显存不足错误。"""
    def __init__(self, required="未知", available="未知"):
        super().__init__(
            f"显存不足: 需要{required}GB, 可用{available}GB",
            "显存不足，请尝试更小的分辨率或等待其他任务完成",
            f"GPU memory insufficient: required {required}GB, available {available}GB"
        )


class NetworkError(StudioError):
    """网络连接错误。"""
    def __init__(self, operation, details):
        super().__init__(
            f"网络操作失败: {operation}",
            "网络连接问题，请检查网络连接或稍后重试",
            f"Network operation failed: {operation} - {details}"
        )


def log(msg: str):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    STATE["detail"] = msg


# ------------------------------------------------------------ 环境自检 ----
def detect_gpu():
    """返回 'rocm' / 'cuda' / 'cpu'。对应文章第二节的环境验证。"""
    try:
        import torch
        if getattr(torch.version, "hip", None) is not None:
            return "rocm"
        if torch.cuda.is_available():
            return "cuda"
    except Exception as e:
        log(f"PyTorch 检测失败：{e}", "warning")
    return "cpu"


def get_gpu_memory_info():
    """获取GPU显存使用情况，提供详细的显存信息。"""
    try:
        import torch
        if torch.cuda.is_available():
            # 获取显存信息
            allocated = torch.cuda.memory_allocated() / 1024**3  # GB
            reserved = torch.cuda.memory_reserved() / 1024**3   # GB

            # 尝试获取总显存
            try:
                total = torch.cuda.get_device_properties(0).total_memory / 1024**3
                free = total - reserved
                return f"总计: {total:.1f}GB, 已分配: {allocated:.1f}GB, 已预留: {reserved:.1f}GB, 可用: {free:.1f}GB"
            except Exception:
                return f"已分配: {allocated:.1f}GB, 已预留: {reserved:.1f}GB"
        return "GPU不可用或未初始化"
    except Exception as e:
        return f"GPU监控失败: {e}"


def cleanup_gpu_resources():
    """清理GPU资源，释放显存。"""
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            gc.collect()
            log("🧹 GPU资源清理完成")
        else:
            log("GPU不可用，跳过资源清理", "debug")
    except Exception as e:
        log(f"GPU资源清理失败: {e}", "warning")


def ensure_comfyui():
    """确保 ComfyUI 源码存在，支持特定版本和多镜像源。
    推荐做法是把 ComfyUI 目录直接提交进创空间仓库（clone 后 rm -rf ComfyUI/.git，见 scripts/setup_comfyui.sh），
    这样构建期无需访问 GitHub。若未提交，则尝试运行时从多个镜像源浅克隆。"""
    main_py = os.path.join(COMFY_DIR, "main.py")
    if os.path.exists(main_py):
        # 检查版本兼容性
        version_file = os.path.join(COMFY_DIR, "VERSION")
        if os.path.exists(version_file):
            with open(version_file) as f:
                version = f.read().strip()
                if version != "0.33.0":  # 文章中使用的版本
                    log(f"ComfyUI版本警告: 检测到{version}, 建议使用0.33.0")
        log("ComfyUI 源码已就绪")
        return

    log("未找到 ComfyUI 源码，尝试从多个镜像源浅克隆……")

    # 多镜像源支持（实测可用的加速镜像优先）
    mirrors = [
        ("https://gh-proxy.com/https://github.com/Comfy-Org/ComfyUI.git", "GitHub加速镜像"),
        ("https://github.com/Comfy-Org/ComfyUI.git", "GitHub官方源"),
    ]

    for mirror, mirror_name in mirrors:
        try:
            log(f"尝试从 {mirror_name} ({mirror}) 克隆ComfyUI……")
            subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", "v0.33.0", mirror, COMFY_DIR],
                check=True, timeout=600,
            )
            log(f"✅ ComfyUI 从 {mirror_name} 克隆完成")
            return
        except Exception as e:
            log(f"❌ 从 {mirror_name} 克隆失败: {e}")
            continue

    raise RuntimeError(
        "ComfyUI 源码缺失且所有镜像源自动克隆失败（可能无法访问 GitHub）。"
        "强烈建议在本地执行 scripts/setup_comfyui.sh 后，把 ComfyUI 目录一起推送进创空间仓库，"
        "这样可避免运行期依赖外部网络。"
    )


def patch_audio_scale():
    """坑2 最小侵入式修复：给 comfy/model_sampling.py 的采样类补 audio_scale 属性。
    ComfyUI 0.33.0 的 ModelSamplingAdvanced 缺少该属性，MiniMax H3 音频解码会 AttributeError。
    新版本若已自带该属性则自动跳过，补丁幂等。"""
    target = os.path.join(COMFY_DIR, "comfy", "model_sampling.py")
    if not os.path.exists(target):
        log("未找到 comfy/model_sampling.py，跳过 audio_scale 补丁（版本可能已修复）")
        return
    with open(target, "r") as f:
        content = f.read()
    classes = re.findall(r"^class (\w+)", content, re.MULTILINE)
    sampling_classes = [c for c in classes if "Sampling" in c]
    patched = 0
    for class_name in sampling_classes:
        if f"{class_name}.audio_scale" in content:
            continue
        pattern = rf"(class {class_name}[^:]*:)"
        if re.search(pattern, content):
            content = re.sub(pattern, r"\1\n    audio_scale = 1.0", content)
            patched += 1
    if patched:
        with open(target, "w") as f:
            f.write(content)
        log(f"audio_scale 补丁完成（{patched} 个采样类）")
    else:
        log("audio_scale 已存在，无需补丁")


# ------------------------------------------------------------ 模型管理 ----
def fix_nested_model_paths():
    """坑1 修复：modelscope download 的 --local-dir 若指错层级会产生
    models/diffusion_models/diffusion_models/xxx 之类的嵌套路径，
    这里自动把文件归位到正确目录。"""
    fixed = []
    for rel, _desc in EXPECTED_MODELS.items():
        dst = os.path.join(MODELS_DIR, rel)
        if os.path.exists(dst):
            continue
        name = os.path.basename(rel)
        hits = [p for p in glob.glob(os.path.join(MODELS_DIR, "**", name), recursive=True)]
        if hits:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(hits[0], dst)
            fixed.append(rel)
    if fixed:
        log(f"已归位嵌套路径模型文件：{fixed}")
    return fixed


def download_models():
    """模型下载函数，支持重试机制、进度显示、断点续传和完整性校验。"""
    if SKIP_MODEL_DOWNLOAD:
        log("SKIP_MODEL_DOWNLOAD=1，跳过模型下载")
        return

    fix_nested_model_paths()

    # 检查已有模型大小，避免重复下载
    existing_size = 0
    for rel in EXPECTED_MODELS:
        dst = os.path.join(MODELS_DIR, rel)
        if os.path.exists(dst):
            try:
                existing_size += os.path.getsize(dst)
            except OSError:
                pass

    if existing_size > 50 * 1024 * 1024 * 1024:  # 50GB
        log(f"✅ 已检测到约{existing_size/(1024**3):.1f}GB模型文件，跳过下载")
        return

    missing = [rel for rel in EXPECTED_MODELS if not os.path.exists(os.path.join(MODELS_DIR, rel))]
    if not missing:
        log("✅ 模型文件齐全，跳过下载")
        return

    log(f"🚀 开始下载模型（共 {len(missing)} 个文件，总大小约52GB，支持断点续传）……")

    for idx, rel in enumerate(missing, 1):
        log(f"📥 下载进度 [{idx}/{len(missing)}]: {rel}（{EXPECTED_MODELS[rel]}）")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 显示下载进度
                process = subprocess.Popen(
                    ["modelscope", "download", "--model", MODEL_REPO, rel, "--local-dir", "models"],
                    cwd=COMFY_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )

                # 实时显示输出，过滤有用信息
                for line in process.stdout:
                    line_stripped = line.strip()
                    if any(keyword in line_stripped for keyword in ["Downloading", "Progress", "完成", "完成", "error", "Error", "失败"]):
                        log(f"  {line_stripped}")

                # 设置更长的超时时间（大文件下载可能需要很长时间）
                try:
                    process.wait(timeout=7200)  # 2小时超时
                except subprocess.TimeoutExpired:
                    process.kill()
                    raise subprocess.TimeoutExpired(process.args, 7200)

                if process.returncode != 0:
                    raise subprocess.CalledProcessError(process.returncode, process.args)

                # 验证文件是否真的下载成功
                dst = os.path.join(MODELS_DIR, rel)
                if os.path.exists(dst):
                    file_size = os.path.getsize(dst)
                    if file_size > 0:
                        log(f"✅ {rel} 下载完成 (大小: {file_size/(1024**3):.2f}GB)")
                        break
                    else:
                        raise RuntimeError(f"下载的文件大小为0: {rel}")
                else:
                    raise RuntimeError(f"下载完成后文件不存在: {rel}")

            except subprocess.TimeoutExpired:
                log(f"⏰ {rel} 下载超时 (尝试 {attempt+1}/{max_retries})")
                if attempt == max_retries - 1:
                    raise RuntimeError(f"{rel} 下载超时，请检查网络连接或手动下载")
                time.sleep(10)  # 等待后重试
            except subprocess.CalledProcessError as e:
                log(f"❌ {rel} 下载失败 (尝试 {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise RuntimeError(f"{rel} 下载失败，请检查网络连接或手动下载")
                time.sleep(5)  # 等待后重试
            except Exception as e:
                log(f"❌ {rel} 下载异常 (尝试 {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise RuntimeError(f"{rel} 下载异常: {e}")
                time.sleep(5)  # 等待后重试

    fix_nested_model_paths()

    # 最终完整性校验
    still_missing = [rel for rel in EXPECTED_MODELS if not os.path.exists(os.path.join(MODELS_DIR, rel))]
    if still_missing:
        raise RuntimeError(f"❌ 模型下载不完整，缺失文件：{still_missing}")

    # 计算总大小
    total_size = 0
    for rel in EXPECTED_MODELS:
        dst = os.path.join(MODELS_DIR, rel)
        if os.path.exists(dst):
            total_size += os.path.getsize(dst)

    log(f"🎉 全部模型下载完成，总大小: {total_size/(1024**3):.2f}GB")


# ------------------------------------------------------------ ComfyUI ----
def comfy_env():
    env = os.environ.copy()
    if detect_gpu() == "rocm":
        # 文章第五节的 MI300X 调优环境变量
        env.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")
        env.setdefault("PYTORCH_TUNABLEOP_ENABLED", "1")
        env.setdefault("HSA_OVERRIDE_GFX_VERSION", "9.4.2")
        env.setdefault("MIOPEN_FIND_MODE", "FAST")
    return env


def start_comfyui():
    if STATE["proc"] is not None and STATE["proc"].poll() is None:
        return
    cmd = [
        "python", "main.py",
        "--port", str(COMFY_PORT),
        "--listen", COMFY_HOST,
        "--enable-cors-header",
        "--enable-compress-response-body",
        "--cache-none",   # 文章建议：AMD 环境下避免显存碎片
    ]
    log("启动 ComfyUI 服务……")
    STATE["proc"] = subprocess.Popen(cmd, cwd=COMFY_DIR, env=comfy_env())


def wait_comfyui(timeout=300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{COMFY_URL}/system_stats", timeout=3)
            if r.status_code == 200:
                STATE["comfy_ready"] = True
                log("ComfyUI 服务已就绪")
                return True
        except requests.RequestException:
            pass
        if STATE["proc"] is not None and STATE["proc"].poll() is not None:
            raise RuntimeError("ComfyUI 进程异常退出，请查看日志")
        time.sleep(2)
    raise RuntimeError("ComfyUI 服务等待超时")


def validate_nodes():
    """启动后校验工作流用到的节点类型在当前 ComfyUI 版本中都存在。"""
    try:
        info = requests.get(f"{COMFY_URL}/object_info", timeout=10).json()
    except Exception as e:
        log(f"节点校验跳过（无法获取 object_info）：{e}")
        return
    needed = ["UNETLoader", "CLIPLoader", "VAELoader", "MiniMaxH3ImageToVideo",
              "RandomNoise", "KSamplerSelect", "PrimitiveInt", "PrimitiveBoolean",
              "LoraLoaderModelOnly", "ComfySwitchNode", "BasicScheduler", "BasicGuider",
              "SamplerCustomAdvanced", "VAEDecode", "VAEDecodeAudio", "CreateVideo", "SaveVideo"]
    missing = [n for n in needed if n not in info]
    if missing:
        log(f"⚠️ 当前 ComfyUI 缺少节点类型：{missing}，请升级 ComfyUI 至 0.30.0+")
    else:
        log("节点完整性校验通过")


# ------------------------------------------------------------ 工作流 ----
def compute_length(duration: float) -> int:
    """官方模板 ComfyMathExpression 的换算公式（17k+5 帧网格，24fps）。"""
    base = max(5, round(duration * 24))
    return base + (5 - (base % 17)) % 17


def build_workflow(prompt, width, height, duration, seed, turbo,
                   base_steps=20, turbo_steps=8, lora_strength=1.0):
    """由官方模板 video_minimax_h3_t2v.json 转换而来的 API 格式工作流。
    视频/音频解码链与模板完全一致（坑3），仅按文章要求替换为 AMD convrot 模型。"""
    length = compute_length(duration)
    return {
        "1":  {"class_type": "UNETLoader", "inputs": {"unet_name": UNET_NAME, "weight_dtype": "default"}},
        "2":  {"class_type": "CLIPLoader", "inputs": {"clip_name": CLIP_NAME, "type": "minimax", "device": "default"}},
        "3":  {"class_type": "VAELoader", "inputs": {"vae_name": VIDEO_VAE_NAME}},
        "4":  {"class_type": "VAELoader", "inputs": {"vae_name": AUDIO_VAE_NAME}},
        "5":  {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
                    "clip": ["2", 0], "vae": ["3", 0],
                    "prompt": prompt, "width": width, "height": height, "length": length}},
        "6":  {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "7":  {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "8":  {"class_type": "PrimitiveInt", "inputs": {"value": base_steps}},
        "9":  {"class_type": "PrimitiveInt", "inputs": {"value": turbo_steps}},
        "10": {"class_type": "PrimitiveBoolean", "inputs": {"value": turbo}},
        "11": {"class_type": "LoraLoaderModelOnly", "inputs": {
                    "model": ["1", 0], "lora_name": LORA_NAME, "strength_model": lora_strength}},
        "12": {"class_type": "ComfySwitchNode", "inputs": {"on_false": ["1", 0], "on_true": ["11", 0], "switch": turbo}},
        "13": {"class_type": "ComfySwitchNode", "inputs": {"on_false": ["8", 0], "on_true": ["9", 0], "switch": turbo}},
        "14": {"class_type": "BasicScheduler", "inputs": {
                    "model": ["12", 0], "steps": ["13", 0], "scheduler": "simple", "denoise": 1}},
        "15": {"class_type": "BasicGuider", "inputs": {"model": ["12", 0], "conditioning": ["5", 0]}},
        "16": {"class_type": "SamplerCustomAdvanced", "inputs": {
                    "noise": ["6", 0], "guider": ["15", 0], "sampler": ["7", 0],
                    "sigmas": ["14", 0], "latent_image": ["5", 1]}},
        "17": {"class_type": "VAEDecode", "inputs": {"samples": ["16", 0], "vae": ["3", 0]}},
        "18": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["16", 0], "vae": ["4", 0]}},
        "19": {"class_type": "CreateVideo", "inputs": {"images": ["17", 0], "audio": ["18", 0], "fps": 24, "bit_depth": 8}},
        "20": {"class_type": "SaveVideo", "inputs": {
                    "video": ["19", 0], "filename_prefix": "MiniMax_H3", "format": "auto", "codec": "auto"}},
    }


# ------------------------------------------------------------ 生成逻辑 ----
def queue_prompt(workflow):
    r = requests.post(f"{COMFY_URL}/prompt", json={"prompt": workflow}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"任务提交失败：{r.text[:500]}")
    return r.json()["prompt_id"]


def fetch_result(prompt_id, started_at):
    """轮询 /history 直到任务完成，返回本地视频文件路径。"""
    deadline = time.time() + GEN_TIMEOUT
    while time.time() < deadline:
        try:
            r = requests.get(f"{COMFY_URL}/history/{prompt_id}", timeout=10)
            data = r.json()
        except requests.RequestException:
            time.sleep(5)
            continue
        if prompt_id not in data:
            time.sleep(5)
            continue
        entry = data[prompt_id]
        status = entry.get("status", {})
        if status.get("completed") is not True:
            time.sleep(5)
            continue
        outputs = entry.get("outputs", {})
        # 1) 优先从 outputs 中找视频文件（SaveVideo 通常挂在 "videos" / "images" 键下）
        candidates = []
        for node_out in outputs.values():
            if not isinstance(node_out, dict):
                continue
            for key in ("videos", "images", "gifs", "files"):
                for item in node_out.get(key, []) or []:
                    if isinstance(item, dict) and item.get("filename"):
                        candidates.append(item)
        for item in candidates:
            if not str(item["filename"]).lower().endswith((".mp4", ".webm", ".mov")):
                continue
            params = {"filename": item["filename"], "type": item.get("type", "output")}
            if item.get("subfolder"):
                params["subfolder"] = item["subfolder"]
            return download_video(params, prompt_id)
        # 2) 兜底：在 ComfyUI/output 下找本次任务新生成的视频
        return find_newest_video(started_at, prompt_id)
    raise RuntimeError("生成超时，请查看 ComfyUI 日志")


def download_video(params, prompt_id):
    r = requests.get(f"{COMFY_URL}/view", params=params, timeout=300)
    r.raise_for_status()
    ext = os.path.splitext(params["filename"])[1] or ".mp4"
    local = os.path.join(OUTPUT_DIR, f"MiniMax_H3_{prompt_id[:8]}{ext}")
    with open(local, "wb") as f:
        f.write(r.content)
    return local


def find_newest_video(started_at, prompt_id):
    files = []
    for ext in ("mp4", "webm", "mov"):
        files += glob.glob(os.path.join(COMFY_DIR, "output", "**", f"*.{ext}"), recursive=True)
    fresh = [f for f in files if os.path.getmtime(f) >= started_at - 5]
    if not fresh:
        raise RuntimeError("任务显示完成但未找到视频文件，请确认工作流未被修改")
    newest = max(fresh, key=os.path.getmtime)
    local = os.path.join(OUTPUT_DIR, f"MiniMax_H3_{prompt_id[:8]}{os.path.splitext(newest)[1]}")
    shutil.copy2(newest, local)
    return local


def generate(prompt, resolution, duration, turbo, seed, status_box):
    """视频生成函数，包含输入验证、错误处理和性能监控。"""
    try:
        # 输入验证
        if not STATE["comfy_ready"]:
            raise gr.Error("后端尚未就绪：" + STATE["detail"])

        # 验证和清理输入
        try:
            validated_prompt = validate_prompt(prompt)
            validated_duration = validate_duration(duration)
            width, height = validate_resolution(resolution)
        except ValueError as e:
            raise gr.Error(f"输入验证失败: {e}")

        if seed is None or seed < 0:
            seed = random.randint(0, 2**63 - 1)

        # 获取任务锁
        if not GEN_LOCK.acquire(blocking=False):
            raise gr.Error("当前已有任务正在运行，请稍后再试（共享GPU限流）")

        try:
            log(f"🎬 提交生成任务：{width}x{height}, {validated_duration}s, turbo={turbo}, seed={seed}")
            yield None, f"🚀 生成中（首次运行需加载约52GB模型到显存，MI300X 192GB可全部常驻，请耐心等待）……"

            # 构建工作流
            wf = build_workflow(validated_prompt, width, height, validated_duration, int(seed), bool(turbo))
            started = time.time()

            # 提交任务
            try:
                prompt_id = queue_prompt(wf)
            except requests.RequestException as e:
                raise NetworkError("提交生成任务", str(e))

            # 等待任务完成并监控进度
            while True:
                try:
                    # 检查队列状态
                    try:
                        q = requests.get(f"{COMFY_URL}/queue", timeout=5).json()
                        running = q.get("queue_running", [])
                        if running and running[0][1] == prompt_id:
                            # 任务正在运行，显示进度
                            pass
                    except requests.RequestException:
                        pass

                    # 检查任务历史
                    r = requests.get(f"{COMFY_URL}/history/{prompt_id}", timeout=10)
                    if r.status_code == 200 and prompt_id in r.json():
                        break

                    time.sleep(5)

                except requests.RequestException as e:
                    log(f"网络请求异常: {e}", "warning")
                    time.sleep(5)
                    continue

            # 获取生成结果
            try:
                video_path = fetch_result(prompt_id, started)
            except requests.RequestException as e:
                raise NetworkError("获取生成结果", str(e))

            cost = int(time.time() - started)
            log(f"🎉 生成完成：{video_path}（耗时 {cost}s）")
            yield video_path, f"✅ 生成完成，耗时 {cost} 秒。"

        finally:
            GEN_LOCK.release()

    except gr.Error:
        raise
    except StudioError as e:
        log(f"❌ 生成失败（StudioError）: {e.message}", "error")
        raise gr.Error(e.user_friendly)
    except requests.RequestException as e:
        log(f"❌ 生成失败（网络错误）: {e}", "error")
        raise gr.Error(f"网络连接问题，请检查网络连接或稍后重试: {str(e)}")
    except subprocess.CalledProcessError as e:
        log(f"❌ 生成失败（子进程错误）: {e}", "error")
        raise gr.Error("ComfyUI后端执行失败，请查看日志了解详情")
    except Exception as e:
        error_msg = str(e)
        log(f"❌ 生成失败（未知错误）: {error_msg}", "error")

        # 根据错误信息提供友好的错误提示
        if "audio_scale" in error_msg:
            friendly_msg = "ComfyUI版本兼容性问题，请重启创空间（应用会在启动时自动修复）"
        elif "out of memory" in error_msg.lower() or "OOM" in error_msg:
            friendly_msg = "显存不足，请尝试更小的分辨率或等待其他任务完成"
        elif "timeout" in error_msg.lower():
            friendly_msg = "生成超时，请重试或减少时长"
        elif "CUDA" in error_msg or "ROCm" in error_msg:
            friendly_msg = "GPU相关错误，请检查GPU状态或重启创空间"
        else:
            friendly_msg = f"生成失败: {error_msg}"

        raise gr.Error(friendly_msg)


def refresh_status():
    """刷新服务状态，提供详细的系统信息。"""
    gpu = detect_gpu()
    gpu_info = {
        "rocm": "AMD ROCm（MI300X 调优已启用）",
        "cuda": "NVIDIA CUDA",
        "cpu": "未检测到 GPU（将使用CPU，速度极慢）"
    }

    gpu_txt = gpu_info.get(gpu, f"未知GPU类型: {gpu}")
    gpu_memory = get_gpu_memory_info()

    status = "✅ 后端就绪，可以生成" if STATE["comfy_ready"] else "⏳ " + STATE["detail"]
    task_status = "🔄 运行中" if GEN_LOCK.locked() else "💤 空闲"

    # 检查磁盘空间
    try:
        total, used, free = shutil.disk_usage(BASE_DIR)
        disk_info = f"磁盘: {free/(1024**3):.1f}GB可用"
    except Exception:
        disk_info = "磁盘: 未知"

    # 检查模型完整性
    model_status = "模型: 检查中..."
    try:
        missing = [rel for rel in EXPECTED_MODELS if not os.path.exists(os.path.join(MODELS_DIR, rel))]
        if not missing:
            model_status = "模型: ✅ 完整"
        else:
            model_status = f"模型: ⚠️ 缺失{len(missing)}个文件"
    except Exception:
        model_status = "模型: ❌ 检查失败"

    return (
        f"🖥️  服务状态：{status}\n"
        f"🎮 GPU类型：{gpu_txt}\n"
        f"💾 显存状态：{gpu_memory}\n"
        f"📊 任务状态：{task_status}\n"
        f"💿 {disk_info}\n"
        f"🤖 {model_status}\n"
        f"📦 模型仓库：{MODEL_REPO}"
    )


# ------------------------------------------------------------ 启动流程 ----
def setup_worker():
    STATE["phase"] = "setup"
    try:
        gpu = detect_gpu()
        log(f"GPU 环境：{'AMD ROCm' if gpu == 'rocm' else gpu}（torch.cuda.is_available 等价检测见 README）")
        ensure_comfyui()
        patch_audio_scale()
        download_models()
        start_comfyui()
        wait_comfyui()
        validate_nodes()
        STATE["phase"] = "ready"
        log("初始化完成，后端就绪")
    except Exception as e:
        STATE["phase"] = "error"
        log(f"初始化失败：{e}")


# ============================================================ Gradio界面构建 ----
CSS = """
footer {display: none !important;}
.gradio-container {font-family: 'Segoe UI', system-ui, sans-serif;}
.status-box {font-family: 'Consolas', monospace; font-size: 12px;}
.example-btn {min-height: 40px !important;}
"""

with gr.Blocks(css=CSS, title="MiniMax H3 视频生成（AMD MI300X 适配）") as demo:
    gr.Markdown(
        "# 🎬 MiniMax H3 文生视频 · AMD MI300X 适配版\n"
        "基于 ComfyUI 官方 MiniMax H3 模板，生成**带原生立体声**的视频。\n"
        "部署与踩坑详解见配套文章："
        "[《192GB 显存真香警告：魔搭 AMD MI300X 部署 ComfyUI + MiniMax H3 的血泪实录》]"
        "(https://www.modelscope.cn/learn/436000)"
    )

    with gr.Row():
        with gr.Column(scale=1):
            # 状态显示
            status_box = gr.Textbox(
                label="📊 服务状态",
                value=refresh_status,
                interactive=False,
                lines=7,
                elem_classes=["status-box"]
            )
            timer = gr.Timer(5)

            with gr.Accordion("📝 示例提示词", open=False):
                gr.Markdown("点击下方按钮快速加载示例提示词：")
                example_buttons = []
                for title, description in EXAMPLE_DESCRIPTIONS.items():
                    with gr.Row():
                        btn = gr.Button(
                            f"{title} - {description}",
                            variant="secondary",
                            elem_classes=["example-btn"]
                        )
                        example_buttons.append((title, btn))

            # 主要输入区域
            prompt_in = gr.Textbox(
                label="🎯 提示词（场景 + 镜头 + 音频一起描述效果最好）",
                value=EXAMPLE_PROMPTS[0][1],  # 默认使用第一个示例
                lines=10,
                placeholder="描述你想要生成的视频内容，包括画面风格、镜头运动、音效等..."
            )

            res_in = gr.Dropdown(
                label="🖼️ 分辨率",
                choices=list(RESOLUTION_PRESETS.keys()),
                value=list(RESOLUTION_PRESETS.keys())[0],
                info="更高分辨率需要更多显存和时间"
            )

            with gr.Row():
                dur_in = gr.Slider(
                    label="⏱️ 时长（秒）",
                    minimum=0.5,
                    maximum=10,
                    step=0.5,
                    value=2,
                    info="时长越长，生成时间越长，建议从2秒开始测试"
                )
                turbo_in = gr.Checkbox(
                    label="🚀 Turbo 模式（8步，推荐）",
                    value=True,
                    info="快速生成模式，质量略降但速度快很多"
                )

            with gr.Row():
                seed_in = gr.Number(
                    label="🎲 随机种子（-1表示随机）",
                    value=-1,
                    precision=0,
                    info="固定种子可重复生成相同结果"
                )

            # 生成按钮
            btn = gr.Button("🎬 生成视频", variant="primary", size="lg")

            # 资源清理按钮
            with gr.Accordion("🔧 高级选项", open=False):
                cleanup_btn = gr.Button("🧹 清理GPU资源", variant="secondary")

                def manual_cleanup():
                    cleanup_gpu_resources()
                    return refresh_status()

                cleanup_btn.click(fn=manual_cleanup, outputs=status_box)

        with gr.Column(scale=1):
            # 视频输出区域
            video_out = gr.Video(label="🎥 生成结果")

            # 使用提示
            gr.Markdown(
                "## 💡 使用提示\n\n"
                "- **首次使用**：需要将约52GB模型加载进显存，MI300X 192GB可全部常驻，请耐心等待；\n"
                "- **进度监控**：采样显示8/8或20/20完成后还需视频/音频VAE解码，属正常现象；\n"
                "- **输出格式**：生成结果为`.mp4`，自带画面与声音。若只得到图片，说明工作流被改动过；\n"
                "- **性能优化**：首次建议从快速预览分辨率开始，生成期间不要提交其他任务；\n"
                "- **时长建议**：建议从2秒开始测试，满意后再增加时长；\n"
                "- **提示词技巧**：详细描述场景、镜头运动、音效可以获得更好的效果。\n\n"
                "## ⚠️ 注意事项\n\n"
                "- 本创空间只暴露Gradio界面，完整ComfyUI UI请按文章在DSW/Notebook中部署；\n"
                "- 显存不足时会自动报错，请尝试更小的分辨率；\n"
                "- 遇到错误请查看上方状态栏的详细错误信息。"
            )

            # 日志显示（可折叠）
            with gr.Accordion("📋 运行日志", open=False):
                log_output = gr.Textbox(
                    label="实时日志",
                    value="启动中...",
                    lines=10,
                    interactive=False
                )
            log_timer = gr.Timer(10)

    # 事件绑定
    timer.tick(fn=refresh_status, outputs=status_box)

    # 示例按钮点击事件
    for title, btn in example_buttons:
        for example_title, example_prompt in EXAMPLE_PROMPTS:
            if example_title == title:
                btn.click(
                    fn=lambda p=example_prompt: p,
                    outputs=prompt_in
                )
                break

    # 生成按钮事件
    btn.click(
        fn=generate,
        inputs=[prompt_in, res_in, dur_in, turbo_in, seed_in, status_box],
        outputs=[video_out, status_box]
    )

    # ==========
    # 日志更新：与状态栏相同的 Timer 轮询机制，跨 Gradio 版本稳定可靠
    def update_log_display():
        try:
            log_file = os.path.join(BASE_DIR, "logs", "studio.log")
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    return ''.join(lines[-20:])  # 显示最后20行
        except Exception:
            pass
        return "日志文件不可用"

    log_timer.tick(fn=update_log_display, outputs=log_output)


if __name__ == "__main__":
    threading.Thread(target=setup_worker, daemon=True).start()
    try:
        # 并发限 1：大模型推理场景串行排队，避免两个任务同时打满 192G 显存
        demo.queue(default_concurrency_limit=1)
    except TypeError:
        # 兼容旧版 Gradio（无 default_concurrency_limit 参数）
        demo.queue()
    port = int(os.environ.get("GRADIO_SERVER_PORT", os.environ.get("PORT", "7860")))
    demo.launch(server_name="0.0.0.0", server_port=port)
