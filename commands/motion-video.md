---
description: 动效视频全流程：需求→导演brief→纯代码渲染方案→成片导出，一句话开工。
argument-hint: "[需求一句话] [--len 秒数] [--ratio 16:9/9:16/1:1]"
---

# /lhg-motion-video:motion-video —— 动效视频全流程

用户输入在 `$ARGUMENTS` 中：`[需求一句话] [--len 秒数] [--ratio 16:9/9:16/1:1]`。如 `/lhg-motion-video:motion-video "新品发布 30 秒宣传片" --len 30 --ratio 16:9`。

## 流程（按顺序加载 4 个 skill 全程指导）

### 1. 导演 brief（加载 lhg-mv-brief）
- 输出 brief.md：需求一句话、受众与投放平台、风格关键词、拍点网格（BPM/关键转场落点）、交付规格（分辨率/帧率/时长/字幕）。
- 用户拍板 brief 后再往下走——动效返工贵，brief 是改需求的唯一依据。

### 2. 渲染方案（加载 lhg-mv-engine）
- 纯代码渲染路线：HTML（seek(t) 确定性时间函数）+ 无头浏览器逐帧渲染 + ffmpeg 合成。不用 After Effects，不买 Remotion 许可。
- 输出：film.json（宽高/帧率/时长/场景清单，唯一可信源）+ render.html（场景实现）+ 素材清单（全部本地化）。
- **静帧先行**：先出 3–5 张关键帧静帧（probe/），用户确认构图配色后再全量渲染。

### 3. 音乐与音效（加载 lhg-mv-audio）
- 按拍点网格选 BGM（自制/已购版权/免费曲库三选一），转场音效按峰值对齐。
- 输出 audio 混音方案：音乐/SFX/（如有）配音三轨说明。

### 4. 渲染与导出（加载 lhg-mv-deliver）
- 探针小样 → 全量渲染 → 混音 → ffmpeg 导出（yuv420p + faststart + crf 16–23 + aac）。
- 输出成片 mp4 + captions.srt（如有字幕）。

### 5. 自查
跑 `/lhg-motion-video:audit`，blocker 清零才算做完。

## 硬规则
- brief 没拍板不许写渲染代码——先定拍点再做动画。
- 没出探针静帧不许全量渲染（hook 会提醒）。
- 导出缺 `-pix_fmt yuv420p` 不许说"成片完成"。
- 素材用外链不许交付（确定性渲染要求全部本地化）。
