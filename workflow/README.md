# 工作流说明

`minimax_h3_t2v_api.json` 由 ComfyUI 官方模板转换而来：

- 来源模板：[`Comfy-Org/workflow_templates` → `templates/video_minimax_h3_t2v.json`](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_t2v.json)
  （即 ComfyUI 界面里 Workflow Templates → Video → MiniMax H3 (Text to Video)）
- 转换方式：UI 格式 → API 格式。子图 `Image to Video (MiniMax H3)` 被展开为普通节点，
  `ResolutionSelector` 和 `ComfyMathExpression` 的计算在 `app.py` 中直接完成
  （分辨率按预设表、帧数按公式 `max(5, round(duration*24)) + (5 - (x % 17)) % 17`）。
- AMD 适配（文章 3.4 节）：CLIPLoader 使用 `qwen3vl_32b_minimax_h3_int8_convrot.safetensors`，
  `type=minimax`；其余节点与官方模板完全一致。

## 如何自定义

**推荐**：直接改 `app.py` 中的 `build_workflow()`，改后用 ComfyUI 界面重新导出 API 格式
（界面中加载官方模板 → 修改 → 菜单「文件 → 导出(API)」）与本文件比对。

**注意（文章坑 3）**：不要手动重搭解码链。视频 Latent 必须走 `VAEDecode`（视频 VAE），
音频 Latent 必须走 `VAEDecodeAudio`（音频 VAE），二者都接 `SamplerCustomAdvanced` 输出，
最后由 `CreateVideo` 合成、`SaveVideo` 保存。任何一环接错都会维度爆炸或只出图片。
