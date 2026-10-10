---
description: 渲染与导出：探针静帧→全量渲染→混音→ffmpeg导出，附渲染耗时预估。
argument-hint: "[影片目录] [--probe-only] [--full]"
---

# /lhg-motion-video:render —— 渲染与导出

用户输入在 `$ARGUMENTS` 中：`[影片目录] [--probe-only] [--full]`。目录缺省为当前目录。

## 流程（加载 lhg-mv-engine 第 4 节 + lhg-mv-deliver）

### 1. 渲染前检查
- film.json 四要素（宽高/帧率/时长/场景）齐全；
- 素材全部本地化（无外链）；
- brief 已拍板。

### 2. 探针静帧（默认先做，`--probe-only` 只做到这步）
- 渲染 3–5 张关键帧静帧到 `probe/`（开场/高潮/结尾必含）。
- 用户确认构图/配色/字体后再往下走。**这一步省掉，返工按分钟计费。**

### 3. 全量渲染（`--full`）
- 无头浏览器逐帧渲染（seek(t) 确定性时间函数，同一输入同一帧）。
- 渲染前报预估耗时（帧数×单帧耗时），超过 10 分钟先跟用户确认。

### 4. 混音与导出
- 音乐/SFX/配音三轨混音（响度目标 -14 LUFS，短视频平台惯例）。
- ffmpeg 导出：`-pix_fmt yuv420p -crf 18 -movflags +faststart -c:a aac -shortest`。
- 输出 `out/final.mp4` + `captions.srt`（如有）。

## 硬规则
- 探针静帧没确认不许 `--full`。
- 导出参数缺 yuv420p/faststart 任一 → 不许交付。
- 渲染耗时不报预估不许开跑（超过 10 分钟要用户点头）。
