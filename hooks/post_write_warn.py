#!/usr/bin/env python3
"""lhg-motion-video 硬门②（警告级，不拦截）：写渲染文件但无探针静帧时提醒。

触发：PostToolUse / Write|Edit。只做提醒，永远 exit 0、不拦截写入。

逃生方式：LHG_MV_HOOKS_OFF=1（环境变量）可关闭本提醒；
或 /plugin disable lhg-motion-video 停用整个插件。
零第三方依赖。
"""

import json
import os
import sys

RENDER_NAMES = {"render.html", "render.py", "render.mjs", "film.html", "scene.html"}


def _has_probe(start_dir):
    d = os.path.abspath(start_dir)
    for _ in range(6):
        probe = os.path.join(d, "probe")
        if os.path.isdir(probe) and os.listdir(probe):
            return True
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return False


def main() -> int:
    if os.environ.get("LHG_MV_HOOKS_OFF") == "1":
        return 0

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0

    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "") or ""
    if not file_path:
        return 0

    base = os.path.basename(file_path).lower()
    if base not in RENDER_NAMES and not base.startswith("render"):
        return 0  # 只关心渲染文件，其余快速放行

    if _has_probe(os.path.dirname(os.path.abspath(file_path))):
        return 0  # 已有探针静帧，不提醒

    msg = (
        "静帧先行提醒（lhg-motion-video）：%s 是渲染文件，但项目里没找到 probe/ 探针静帧。\n"
        "动效管线的纪律是先看静帧、再全量渲染：静帧阶段调构图配色成本最低，\n"
        "跳过这步直接全量渲染，返工时按分钟计费。建议先出 3-5 张关键帧静帧确认后再渲染。\n"
        "确认不需要探针时忽略本提醒。\n"
        "关闭本提醒：export LHG_MV_HOOKS_OFF=1（当前会话有效）。"
    ) % file_path
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": msg,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
