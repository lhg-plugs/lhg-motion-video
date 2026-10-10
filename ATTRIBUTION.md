# 灵感来源与致谢（Attribution）

本插件的**方法论灵感**来自以下优秀的开源项目，**所有实现代码、检测规则与文案均为原创**，未复制任何第三方的原文案与代码。

| 项目 | 作者 / 组织 | 许可 | 链接 | 借鉴了什么思路 |
|---|---|---|---|---|
| claude-motion-design | howseen-ai（Raphaël Aubry） | MIT | https://github.com/howseen-ai/claude-motion-design | "纯代码做动效（HTML+无头浏览器+ffmpeg），不要 After Effects"的路线；seek(t) 确定性逐帧渲染思想；先摆拍点网格（beat map）再做动画；静帧先行（probe stills）看效果再全量渲染；音效按峰值对齐。本插件的渲染管线设计受其启发，**全部代码与文案均为原创重写** |
| awesome-opus-video-skills | ismoshushi | 未声明（仅作生态索引参考） | https://github.com/ismoshushi/awesome-opus-video-skills | 代码渲染类视频 skill 的生态全景（多种渲染栈对比），用于本插件"渲染方案选型"章节的问题意识 |

## 声明

1. **借鉴思路，实现与文案均为原创**：以上项目的具体文案、代码实现均未被复制。本插件的 skill 方法论文案、审计规则、命令流程、渲染脚本模板均为独立撰写。
2. **许可合规**：howseen-ai/claude-motion-design 为 MIT 许可，允许在保留声明的前提下进行思路借鉴与二次创作，本文件即为保留声明的一部分；未声明许可的项目仅作生态索引参考，未借鉴其表达。
3. **商标与归属**：各项目名称与作者署名归其各自所有者所有。

## 本插件自身的许可

本插件原创部分采用 MIT 许可（见 `LICENSE` 文件），版权所有：刘洪光（https://github.com/lhg-skills）。
