#!/usr/bin/env python3
"""lhg-motion-video 确定性成片审计：28 条规则，零第三方依赖。

扫描一个纯代码动效视频项目的交付目录（film.json / 渲染 HTML /
导出脚本 / captions.srt / brief.md / assets/），输出 JSON 与人类可读报告；
有 blocker 时以非零 exit code 退出（供 hooks 与 CI 使用）。

用法：
    python3 motion_audit.py --target <影片目录> [--format json|text] [--fail-on blocker|warning|nit]

规则文案均为本项目原创（渲染管线思路受 howseen-ai/claude-motion-design 启发，
未复制其任何原文与代码）。
"""

import argparse
import json
import os
import re
import sys

VERSION = "1.0.0"
TOOL = "lhg-motion-video/motion-audit"

SKIP_DIRS = {".git", "__pycache__", "node_modules", "dist", "build", "out"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a", ".aac"}
MEDIA_EXTS = {".png", ".jpg", ".jpeg", ".svg", ".mp4", ".webm", ".gif"}
COMMON_SPECS = {(1920, 1080), (1280, 720), (3840, 2160), (1080, 1920), (1080, 1080)}


class Finding:
    __slots__ = ("rule_id", "severity", "category", "title", "file", "line", "snippet", "detail")

    def __init__(self, rule_id, severity, category, title, file, line, snippet, detail):
        self.rule_id = rule_id
        self.severity = severity
        self.category = category
        self.title = title
        self.file = file
        self.line = line
        self.snippet = snippet
        self.detail = detail

    def to_dict(self):
        return {
            "rule_id": self.rule_id, "severity": self.severity,
            "category": self.category, "title": self.title,
            "file": self.file, "line": self.line,
            "snippet": self.snippet, "detail": self.detail,
        }


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def srt_to_seconds(ts):
    m = re.match(r"(\d+):(\d{2}):(\d{2})[,.](\d{1,3})", ts)
    if not m:
        return None
    h, mi, s, ms = [int(x) for x in m.groups()]
    return h * 3600 + mi * 60 + s + int(ms) / 1000.0


def parse_srt(text):
    """返回 [(序号, 开始秒, 结束秒, 文本)]。"""
    out = []
    blocks = re.split(r"\n\s*\n", text.strip())
    for b in blocks:
        lines = b.strip().split("\n")
        if len(lines) < 2:
            continue
        m = re.match(r"(\d+)", lines[0].strip())
        idx = int(m.group(1)) if m else 0
        tm = re.search(r"(\d+:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d+:\d{2}:\d{2}[,.]\d{1,3})", lines[1])
        if not tm:
            continue
        s, e = srt_to_seconds(tm.group(1)), srt_to_seconds(tm.group(2))
        if s is None or e is None:
            continue
        out.append((idx, s, e, " ".join(lines[2:]).strip()))
    return out


# ---------------------------------------------------------------- 规则注册表

RULES = []
_RULE_BY_ID = {}


def rule(rule_id, severity, category, title, detail):
    def deco(fn):
        r = {"id": rule_id, "severity": severity, "category": category,
             "title": title, "detail": detail}
        _RULE_BY_ID[rule_id] = r
        r["check"] = fn
        RULES.append(r)
        return fn
    return deco


def _mk(rule_id, path, line, snippet):
    r = _RULE_BY_ID[rule_id]
    return Finding(r["id"], r["severity"], r["category"], r["title"],
                   path, line, snippet[:160], r["detail"])


def _collect(target):
    ctx = {"target": target, "film": None, "film_data": None,
           "htmls": [], "scripts": [], "export_cmd": "", "export_file": None,
           "srt": None, "brief": None, "probe_files": [], "asset_files": set(),
           "refs": []}  # refs: [(引用串, 来源文件, 行号)]
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            p = os.path.join(root, f)
            rel = os.path.relpath(p, target)
            low = f.lower()
            if low == "film.json" and ctx["film"] is None:
                ctx["film"] = p
                try:
                    ctx["film_data"] = json.loads(read_text(p))
                except Exception:
                    ctx["film_data"] = None
            elif low.endswith(".html"):
                ctx["htmls"].append(p)
            elif low.endswith((".py", ".js", ".mjs")):
                ctx["scripts"].append(p)
            elif low in ("export.sh", "export.txt", "mux.sh") and ctx["export_file"] is None:
                ctx["export_file"] = p
                ctx["export_cmd"] = read_text(p)
            elif low in ("captions.srt", "subs.srt", "subtitles.srt") and ctx["srt"] is None:
                ctx["srt"] = p
            elif low == "brief.md" and ctx["brief"] is None:
                ctx["brief"] = p
            if "probe" in rel.replace("\\", "/").split("/"):
                ctx["probe_files"].append(p)
            if rel.replace("\\", "/").startswith("assets/"):
                ctx["asset_files"].add(rel.replace("\\", "/"))
    # 收集代码中的素材引用
    for p in ctx["htmls"] + ctx["scripts"]:
        for i, ln in enumerate(read_text(p).split("\n")):
            for m in re.finditer(r"""["']((?:assets/|https?://)[^"'\)\s]+)["']""", ln):
                ctx["refs"].append((m.group(1), p, i + 1))
    if ctx["export_file"] is None:
        # 兜底：在任意 sh/txt 里找 ffmpeg 命令
        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if f.lower().endswith((".sh", ".txt", ".md")):
                    p = os.path.join(root, f)
                    t = read_text(p)
                    if "ffmpeg" in t and ctx["export_file"] is None:
                        ctx["export_file"] = p
                        ctx["export_cmd"] = t
    return ctx


def _canvas_size(ctx):
    for p in ctx["htmls"]:
        t = read_text(p)
        m = re.search(r"<canvas[^>]*width\s*=\s*[\"']?(\d+)[\"']?[^>]*height\s*=\s*[\"']?(\d+)", t, re.I)
        if m:
            return int(m.group(1)), int(m.group(2)), p
        m = re.search(r"<canvas[^>]*height\s*=\s*[\"']?(\d+)[\"']?[^>]*width\s*=\s*[\"']?(\d+)", t, re.I)
        if m:
            return int(m.group(2)), int(m.group(1)), p
        mw = re.search(r"\b(?:W|WIDTH|width)\s*[:=]\s*(\d{3,4})\b", t)
        mh = re.search(r"\b(?:H|HEIGHT|height)\s*[:=]\s*(\d{3,4})\b", t)
        if mw and mh:
            return int(mw.group(1)), int(mh.group(1)), p
    return None


def _script_fps(ctx):
    for p in ctx["htmls"] + ctx["scripts"]:
        t = read_text(p)
        m = re.search(r"\b(?:FPS|fps|frameRate)\s*[:=]\s*(\d+(?:\.\d+)?)", t)
        if m:
            return float(m.group(1)), p
        m = re.search(r"--fps\s+(\d+(?:\.\d+)?)", t)
        if m:
            return float(m.group(1)), p
    return None


# ---------------- manifest ----------------

@rule("MV-MF-001", "blocker", "manifest", "film.json 缺失",
      "没有 film.json，渲染尺寸、帧率、时长就没有唯一可信源，各脚本各说各话，成片一定翻车。")
def r_mf_001(ctx):
    if ctx["film"] is None:
        return [_mk("MV-MF-001", ctx["target"], 0, "无 film.json")]
    return []


@rule("MV-MF-002", "blocker", "manifest", "film.json 缺 width/height/fps/duration",
      "宽高帧率时长是渲染管线的四根柱子，缺一根，后续所有一致性检查都无从谈起。")
def r_mf_002(ctx):
    if not ctx["film_data"]:
        return []
    missing = [k for k in ("width", "height", "fps", "duration")
               if k not in ctx["film_data"]]
    if missing:
        return [_mk("MV-MF-002", ctx["film"], 0, "缺字段: %s" % ", ".join(missing))]
    return []


@rule("MV-MF-003", "warning", "manifest", "分辨率非常见规格",
      "不是 1920x1080 / 1280x720 / 3840x2160 / 1080x1920 / 1080x1080 这类常见规格，"
      "确认是故意的（如特殊装置屏），否则换成常见规格省掉一堆兼容坑。")
def r_mf_003(ctx):
    if not ctx["film_data"]:
        return []
    w, h = ctx["film_data"].get("width"), ctx["film_data"].get("height")
    if isinstance(w, int) and isinstance(h, int) and (w, h) not in COMMON_SPECS:
        return [_mk("MV-MF-003", ctx["film"], 0, "%dx%d" % (w, h))]
    return []


@rule("MV-MF-004", "nit", "manifest", "film.json 缺 title/description",
      "成片标题和一句话简介是分发时的 SEO 原料，现在不写，发布那天还得回来补。")
def r_mf_004(ctx):
    if not ctx["film_data"]:
        return []
    missing = [k for k in ("title", "description") if not ctx["film_data"].get(k)]
    if missing:
        return [_mk("MV-MF-004", ctx["film"], 0, "缺字段: %s" % ", ".join(missing))]
    return []


# ---------------- 渲染一致性 ----------------

@rule("MV-REN-001", "blocker", "渲染", "canvas 尺寸与 film.json 宽高不一致",
      "HTML 画布尺寸和 film.json 声明的不一样，渲染出来的成片和预期的分辨率对不上，"
      "属于改了一处忘改另一处。")
def r_ren_001(ctx):
    if not ctx["film_data"]:
        return []
    cs = _canvas_size(ctx)
    if not cs:
        return []
    w, h, p = cs
    fw, fh = ctx["film_data"].get("width"), ctx["film_data"].get("height")
    if (w, h) != (fw, fh):
        return [_mk("MV-REN-001", p, 0, "画布 %dx%d vs film.json %sx%s" % (w, h, fw, fh))]
    return []


@rule("MV-REN-002", "blocker", "渲染", "渲染脚本帧率与 film.json 不一致",
      "渲染用的 fps 和 film.json 声明的不一样，时长和拍点会对不上——"
      "30fps 按 24fps 渲染，60 秒的片子会变成 75 秒。")
def r_ren_002(ctx):
    if not ctx["film_data"]:
        return []
    sf = _script_fps(ctx)
    if not sf:
        return []
    fps, p = sf
    ffps = ctx["film_data"].get("fps")
    if ffps and abs(fps - ffps) > 0.01:
        return [_mk("MV-REN-002", p, 0, "脚本 %s fps vs film.json %s fps" % (fps, ffps))]
    return []


@rule("MV-REN-003", "warning", "渲染", "场景时长总和与 film.json duration 偏差超 0.5s",
      "各场景时长加起来和总时长对不上，说明有场景改了时长没同步，成片会多出/缺失一截。")
def r_ren_003(ctx):
    if not ctx["film_data"]:
        return []
    scenes = ctx["film_data"].get("scenes")
    dur = ctx["film_data"].get("duration")
    if not isinstance(scenes, list) or not isinstance(dur, (int, float)):
        return []
    total = sum(float(s.get("duration", 0) or 0) for s in scenes if isinstance(s, dict))
    if abs(total - dur) > 0.5:
        return [_mk("MV-REN-003", ctx["film"], 0,
                    "场景合计 %.1fs vs 声明 %.1fs" % (total, dur))]
    return []


@rule("MV-REN-004", "warning", "渲染", "单个场景超过 30 秒",
      "动效视频里单个场景超过 30 秒没有视觉变化，观众流失风险陡增。拆成两个场景或加转场。")
def r_ren_004(ctx):
    if not ctx["film_data"]:
        return []
    scenes = ctx["film_data"].get("scenes")
    if not isinstance(scenes, list):
        return []
    return [_mk("MV-REN-004", ctx["film"], 0,
                "%s %.0fs" % (s.get("name", "?"), s.get("duration", 0)))
            for s in scenes if isinstance(s, dict)
            and isinstance(s.get("duration"), (int, float)) and s["duration"] > 30]


@rule("MV-REN-005", "nit", "渲染", "3 个以上场景无转场说明",
      "场景之间没有转场（切/叠/推），成片会像 PPT 翻页。至少给每个场景标一个转场方式。")
def r_ren_005(ctx):
    if not ctx["film_data"]:
        return []
    scenes = ctx["film_data"].get("scenes")
    if not isinstance(scenes, list):
        return []
    n = sum(1 for s in scenes if isinstance(s, dict) and not s.get("transition"))
    if n >= 3:
        return [_mk("MV-REN-005", ctx["film"], 0, "%d 个场景无转场" % n)]
    return []


@rule("MV-REN-006", "warning", "渲染", "总时长超过 180 秒",
      "动效宣传片超过 3 分钟，完播率通常断崖下跌。确认不是把长视频硬塞进动效壳子里。")
def r_ren_006(ctx):
    if not ctx["film_data"]:
        return []
    dur = ctx["film_data"].get("duration")
    if isinstance(dur, (int, float)) and dur > 180:
        return [_mk("MV-REN-006", ctx["film"], 0, "%.0fs" % dur)]
    return []


@rule("MV-QA-001", "warning", "渲染", "无探针静帧产物",
      "没有 probe/ 静帧探针。动效讲究先看静帧、再全量渲染：静帧阶段调构图配色成本最低，"
      "跳过这步等于闭眼渲染，返工时按分钟计费。")
def r_qa_001(ctx):
    if not ctx["probe_files"]:
        return [_mk("MV-QA-001", ctx["target"], 0, "无 probe/ 目录或为空")]
    return []


# ---------------- 字幕 ----------------

@rule("MV-CAP-001", "blocker", "字幕", "字幕时间重叠",
      "两条字幕时间轴重叠，播放时会两行糊在一起。检查切分点是否写错。")
def r_cap_001(ctx):
    if ctx["srt"] is None:
        return []
    subs = parse_srt(read_text(ctx["srt"]))
    hits = []
    for (i1, s1, e1, _), (i2, s2, e2, _) in zip(subs, subs[1:]):
        if s2 < e1 - 0.001:
            hits.append(_mk("MV-CAP-001", ctx["srt"], 0,
                            "#%d 与 #%d 重叠" % (i1, i2)))
    return hits


@rule("MV-CAP-002", "warning", "字幕", "字幕单行超过 20 个中文字符",
      "中文观众一行的舒适阅读量约 20 字以内，超了就得拆成两行或缩短显示时长。按字符数算，标点也算。")
def r_cap_002(ctx):
    if ctx["srt"] is None:
        return []
    hits = []
    for idx, s, e, text in parse_srt(read_text(ctx["srt"])):
        for line in text.split(" "):
            t = line.strip()
            if len(t) > 20:
                hits.append(_mk("MV-CAP-002", ctx["srt"], 0,
                                "#%d %d 字" % (idx, len(t))))
                break
    return hits


@rule("MV-CAP-003", "warning", "字幕", "字幕显示时长小于 1s 或大于 7s",
      "小于 1 秒看不清，大于 7 秒像卡住了。按 20 字/行、每秒 4–5 字的速度估算时长。")
def r_cap_003(ctx):
    if ctx["srt"] is None:
        return []
    return [_mk("MV-CAP-003", ctx["srt"], 0, "#%d %.1fs" % (idx, e - s))
            for idx, s, e, _ in parse_srt(read_text(ctx["srt"]))
            if (e - s) < 1 or (e - s) > 7]


@rule("MV-CAP-004", "warning", "字幕", "字幕安全区未声明",
      "film.json 里没有 caption_safe_margin。字幕贴边会被平台 UI（标题/按钮）遮挡，"
      "声明安全边距（如 0.9 表示只用画面中央 90% 区域）。")
def r_cap_004(ctx):
    if ctx["srt"] is None or not ctx["film_data"]:
        return []
    if "caption_safe_margin" not in ctx["film_data"]:
        return [_mk("MV-CAP-004", ctx["film"], 0, "缺 caption_safe_margin")]
    return []


@rule("MV-CAP-005", "nit", "字幕", "SRT 序号不连续",
      "序号跳号不影响播放，但说明字幕文件被手工改过，容易藏着时间轴错误，顺手理一下。")
def r_cap_005(ctx):
    if ctx["srt"] is None:
        return []
    subs = parse_srt(read_text(ctx["srt"]))
    idxs = [i for i, _, _, _ in subs if i]
    if idxs and idxs != list(range(1, len(idxs) + 1)):
        return [_mk("MV-CAP-005", ctx["srt"], 0, "序号: %s" % idxs[:6])]
    return []


# ---------------- 导出 ----------------

def _export_flags(cmd):
    return {
        "pix_fmt": re.search(r"-pix_fmt\s+(\S+)", cmd),
        "faststart": "faststart" in cmd,
        "crf": re.search(r"-crf\s+(\d+)", cmd),
        "audio_codec": re.search(r"-c:a\s+(\S+)", cmd),
        "size_s": re.search(r"-s\s+(\d+)x(\d+)", cmd),
        "size_scale": re.search(r"scale=(\d+):(\d+)", cmd),
        "shortest": "-shortest" in cmd,
    }


@rule("MV-EXP-001", "blocker", "导出", "导出命令缺 -pix_fmt yuv420p",
      "缺了 yuv420p，QuickTime 和部分浏览器放出来会偏色或直接黑屏。这是兼容性红线。")
def r_exp_001(ctx):
    if not ctx["export_cmd"]:
        return []
    fl = _export_flags(ctx["export_cmd"])
    if not fl["pix_fmt"] or fl["pix_fmt"].group(1) != "yuv420p":
        return [_mk("MV-EXP-001", ctx["export_file"], 0, "缺 -pix_fmt yuv420p")]
    return []


@rule("MV-EXP-002", "warning", "导出", "导出命令缺 -movflags +faststart",
      "缺了 faststart，moov box 沉在文件尾，网页播放要等整个文件下载完才开始，体验极差。")
def r_exp_002(ctx):
    if not ctx["export_cmd"]:
        return []
    fl = _export_flags(ctx["export_cmd"])
    if not fl["faststart"]:
        return [_mk("MV-EXP-002", ctx["export_file"], 0, "缺 -movflags +faststart")]
    return []


@rule("MV-EXP-003", "warning", "导出", "crf 超出 14–28 合理区间",
      "crf 太小文件巨大（14 以下收益递减），太大画质糊（28 以上文字边缘发虚）。"
      "动效视频文字多，建议 16–23。")
def r_exp_003(ctx):
    if not ctx["export_cmd"]:
        return []
    fl = _export_flags(ctx["export_cmd"])
    if fl["crf"]:
        crf = int(fl["crf"].group(1))
        if crf < 14 or crf > 28:
            return [_mk("MV-EXP-003", ctx["export_file"], 0, "crf=%d" % crf)]
    return []


@rule("MV-EXP-004", "warning", "导出", "音频编码不是 aac",
      "mp4 容器配 aac 是通用性最好的组合。用 libmp3lame 等非常规编码，"
      "部分播放器会静音或报错。")
def r_exp_004(ctx):
    if not ctx["export_cmd"]:
        return []
    fl = _export_flags(ctx["export_cmd"])
    if fl["audio_codec"] and fl["audio_codec"].group(1) != "aac":
        return [_mk("MV-EXP-004", ctx["export_file"], 0,
                    "-c:a %s" % fl["audio_codec"].group(1))]
    return []


@rule("MV-EXP-005", "blocker", "导出", "导出分辨率与 film.json 不一致",
      "导出命令里指定的分辨率和 film.json 对不上，成片会被拉伸或留黑边，"
      "属于改了一处忘改另一处。")
def r_exp_005(ctx):
    if not ctx["export_cmd"] or not ctx["film_data"]:
        return []
    fl = _export_flags(ctx["export_cmd"])
    fw, fh = ctx["film_data"].get("width"), ctx["film_data"].get("height")
    got = None
    if fl["size_s"]:
        got = (int(fl["size_s"].group(1)), int(fl["size_s"].group(2)))
    elif fl["size_scale"]:
        got = (int(fl["size_scale"].group(1)), int(fl["size_scale"].group(2)))
    if got and (fw, fh) and got != (fw, fh):
        return [_mk("MV-EXP-005", ctx["export_file"], 0,
                    "导出 %dx%d vs film.json %sx%s" % (got[0], got[1], fw, fh))]
    return []


@rule("MV-EXP-006", "nit", "导出", "导出命令缺 -shortest",
      "音频比视频长时，缺了 -shortest 会在结尾多出一截黑屏/静音。加上它让音画同收。")
def r_exp_006(ctx):
    if not ctx["export_cmd"]:
        return []
    fl = _export_flags(ctx["export_cmd"])
    if not fl["shortest"]:
        return [_mk("MV-EXP-006", ctx["export_file"], 0, "缺 -shortest")]
    return []


# ---------------- 素材 ----------------

@rule("MV-AST-001", "blocker", "素材", "代码引用的本地素材文件不存在",
      "渲染脚本里引用了 assets/ 下的文件，但文件不存在。渲染时会缺图/报错，"
      "属于提交了半成品。")
def r_ast_001(ctx):
    hits = []
    for ref, p, ln in ctx["refs"]:
        if ref.startswith("http"):
            continue
        ext = os.path.splitext(ref)[1].lower()
        if ext in AUDIO_EXTS:
            continue  # 音频走 MV-AST-002
        if ref not in ctx["asset_files"]:
            hits.append(_mk("MV-AST-001", p, ln, ref))
    return hits


@rule("MV-AST-002", "warning", "素材", "引用的音乐/SFX 文件不存在",
      "引用了音乐或音效文件但文件缺失。成片会静音或混音失败，"
      "先确认是占位还是真丢了。")
def r_ast_002(ctx):
    hits = []
    for ref, p, ln in ctx["refs"]:
        if ref.startswith("http"):
            continue
        ext = os.path.splitext(ref)[1].lower()
        if ext in AUDIO_EXTS and ref not in ctx["asset_files"]:
            hits.append(_mk("MV-AST-002", p, ln, ref))
    return hits


@rule("MV-AST-003", "nit", "素材", "素材文件名含空格或中文",
      "文件名里的空格/中文在 ffmpeg 命令与跨平台路径里容易出转义问题，"
      "建议小写英文+连字符，现在改成本最低。")
def r_ast_003(ctx):
    return [_mk("MV-AST-003", os.path.join(ctx["target"], rel), 0,
                os.path.basename(rel))
            for rel in ctx["asset_files"]
            if re.search(r"\s|[^\x00-\x7f]", os.path.basename(rel))]


@rule("MV-AST-004", "warning", "素材", "引用了 http(s) 外链素材",
      "代码里直接引用外链图片/音频，别人复现渲染时可能 404，"
      "且外链内容变了成片就变了。确定性渲染要求素材全部本地化。")
def r_ast_004(ctx):
    hits = []
    for ref, p, ln in ctx["refs"]:
        if ref.startswith("http"):
            ext = os.path.splitext(ref.split("?")[0])[1].lower()
            if ext in MEDIA_EXTS or ext in AUDIO_EXTS or not ext:
                hits.append(_mk("MV-AST-004", p, ln, ref[:80]))
    return hits


# ---------------- 导演 brief ----------------

@rule("MV-BRIEF-001", "warning", "brief", "无导演 brief 文件",
      "没有 brief.md，需求、受众、风格、交付规格全靠口头，后续改需求没有依据。"
      "动效返工贵，先写 brief 再写代码。")
def r_brief_001(ctx):
    if ctx["brief"] is None:
        return [_mk("MV-BRIEF-001", ctx["target"], 0, "无 brief.md")]
    return []


@rule("MV-BRIEF-002", "warning", "brief", "brief 缺拍点/节拍说明",
      "brief 里没有拍点网格（beat map / BPM / 节拍），音乐卡点只能靠感觉。"
      "先定节拍再做动画，这是代码动效区别于凭感觉剪辑的关键。")
def r_brief_002(ctx):
    if ctx["brief"] is None:
        return []
    t = read_text(ctx["brief"])
    if not re.search(r"beat|拍点|节拍|BPM|bpm|卡点", t):
        return [_mk("MV-BRIEF-002", ctx["brief"], 0, "无拍点说明")]
    return []


# ---------------------------------------------------------------- 主流程

SEV_ORDER = {"blocker": 0, "warning": 1, "nit": 2}


def run_audit(target):
    ctx = _collect(target)
    findings = []
    for r in RULES:
        try:
            findings.extend(r["check"](ctx))
        except Exception as e:
            findings.append(Finding(r["id"], "nit", "脚本", "规则执行异常",
                                    target, 0, str(e)[:120],
                                    "规则内部出错，已 fail-open 跳过，不影响其他规则。"))
    findings.sort(key=lambda f: (SEV_ORDER[f.severity], f.rule_id, f.file, f.line))
    sev = {"blocker": 0, "warning": 0, "nit": 0}
    for f in findings:
        sev[f.severity] += 1
    return {
        "tool": TOOL, "version": VERSION, "target": os.path.abspath(target),
        "summary": {"blocker": sev["blocker"], "warning": sev["warning"],
                    "nit": sev["nit"], "rules_run": len(RULES)},
        "findings": [f.to_dict() for f in findings],
    }


def format_text(data):
    lines = ["[%s v%s] 目标: %s" % (data["tool"], data["version"], data["target"])]
    s = data["summary"]
    lines.append("规则 %d 条 → blocker %d / warning %d / nit %d"
                 % (s["rules_run"], s["blocker"], s["warning"], s["nit"]))
    for f in data["findings"]:
        loc = "%s:%s" % (f["file"], f["line"]) if f["line"] else f["file"]
        lines.append("[%s][%s] %s\n    %s → %s"
                     % (f["severity"], f["rule_id"], f["title"], loc, f["detail"][:90]))
    if not data["findings"]:
        lines.append("干净：无发现。")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--format", choices=["json", "text"], default="json")
    ap.add_argument("--fail-on", choices=["blocker", "warning", "nit"], default="blocker")
    args = ap.parse_args()
    data = run_audit(args.target)
    if args.format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(format_text(data))
    n = data["summary"][args.fail_on]
    if args.fail_on == "warning":
        n += data["summary"]["blocker"]
    elif args.fail_on == "nit":
        n += data["summary"]["blocker"] + data["summary"]["warning"]
    return 2 if n > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
