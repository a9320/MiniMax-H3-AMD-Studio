# -*- coding: utf-8 -*-
"""文章坑2 独立修复工具：ComfyUI 0.33.0 的 ModelSamplingAdvanced 缺少 audio_scale 属性，
MiniMax H3 音频解码阶段会报 AttributeError。本脚本做最小侵入式补丁，幂等可重复执行。
用法：python scripts/fix_audio_scale.py [ComfyUI目录]
"""
import re
import sys
from pathlib import Path

comfy_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "ComfyUI"
target = comfy_dir / "comfy" / "model_sampling.py"
if not target.exists():
    print(f"未找到 {target}，可能版本已修复或路径不对，退出")
    sys.exit(0)

content = target.read_text(encoding="utf-8")
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
    target.write_text(content, encoding="utf-8")
print(f"✅ audio_scale 修复完成（{patched} 个采样类）" if patched else "audio_scale 已存在，无需修复")
