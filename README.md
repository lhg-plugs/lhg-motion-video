<!-- About 简介（推送后填写到仓库 About 栏）：
动效视频专家：需求→导演brief→纯代码渲染→成片导出 ｜ 一键安装：/plugin marketplace add lhg-plugs/lhg-motion-video
-->
<!-- topics（推送后打）：claude-code, claude-plugin, agent-skills, motion-design, ffmpeg, video -->

# lhg-motion-video：动效视频专家

> **一句话介绍**：一句话开工一条动效视频——导演 brief（分镜+拍点网格）→纯代码渲染方案（seek(t) 确定性时间函数，不用 After Effects）→探针静帧确认→全量渲染→混音导出，28 条确定性规则发布前自检。
>
> **一键安装**：在 Claude Code 里运行
> ```
> /plugin marketplace add lhg-plugs/lhg-motion-video
> /plugin install lhg-motion-video@lhg-plugs
> ```

## 它是什么

`lhg-motion-video` 是一个 Claude Code 插件（plugin 为主、skill 为辅），专为"想做片头/转场/产品宣传片但不会 After Effects"的小白设计：

- **4 个命令**（小白入口）：`motion-video` 动效全流程（需求→brief→渲染→导出），`brief` 只做导演 brief（分镜+拍点网格），`render` 渲染与导出（探针静帧→全量→混音），`audit` 成片体检
- **4 个平台中立 skill**（方法论，可移植到豆包/Workbuddy 等 agent 平台）：导演 brief、纯代码渲染引擎、音乐与音效、导出与质检
- **2 个专家 agent**：动效导演（端到端执行）、独立审计员（发布前挑毛病）
- **2 个硬门 hooks**：commit 前成片审计拦截、写渲染文件无探针静帧提醒（均可一键豁免）
- **28 条确定性自查规则**：分辨率/帧率一致性、场景时长、字幕安全区、导出编码参数（yuv420p/faststart）、素材缺失，纯 Python、零第三方依赖，5 秒出结果

工作流：`brief`（定方向）→ `motion-video`（出成片）→ `audit`（查一遍），也可以只用其中一段。

## 4 个命令用法

| 命令 | 作用 | 示例 |
|---|---|---|
| `/lhg-motion-video:motion-video` | 动效全流程：需求→brief→纯代码渲染→成片导出 | `/lhg-motion-video:motion-video "新品发布30秒宣传片" --len 30 --ratio 16:9` |
| `/lhg-motion-video:brief` | 只做导演 brief：5 问澄清→分镜→拍点网格→交付规格 | `/lhg-motion-video:brief "咖啡店开业15秒竖屏广告"` |
| `/lhg-motion-video:render` | 渲染与导出：探针静帧→全量渲染→混音→ffmpeg | `/lhg-motion-video:render ./my-film/ --full` |
| `/lhg-motion-video:audit` | 成片体检（脚本 + 人工评审清单） | `/lhg-motion-video:audit ./my-film/` |

## 为什么用纯代码，不用剪辑软件

| 维度 | 纯代码（本插件路线） | 剪辑软件 |
|---|---|---|
| 确定性 | seek(t) 函数，修 A 场景不影响 B | 时间轴手工拖，易误触 |
| 成本 | 免费（浏览器+ffmpeg 开源） | 订阅费/买断费 |
| AI 协作 | "转场再快 0.2 秒"=改个数字 | 得 reopen 工程手工调 |
| 版本管理 | git diff 看得见每一帧的逻辑 | 二进制工程文件 diff 无意义 |

一句话：动效片是"算"出来的，不是"拖"出来的。

## 自查说明

自查 = 确定性脚本（机器）+ 人工评审清单（人）：

1. 先跑 `scripts/audit/motion_audit.py`（28 条规则：manifest 4、渲染 7、字幕 5、导出 6、素材 4、brief 2），零 LLM 成本；
2. 发现分三级：**blocker**（必须修，尺寸/帧率不一致、缺 yuv420p、字幕重叠、素材缺失，commit 前 hook 会拦截）、**warning**（修或写豁免理由）、**nit**（顺手修）；
3. 再按 `lhg-mv-deliver` 第 5 节的人工评审清单过一遍脚本抓不到的（转场抽帧、听画对位、画面真实性、手机/电脑实际播放验证）。

blocker 清零才算可发布；为清零改规则算作弊，不许。

## 目录结构

```
lhg-motion-video/
├── .claude-plugin/          # plugin.json（插件清单）+ marketplace.json（本仓即市场）
├── commands/                # 4 个命令：motion-video / brief / render / audit
├── skills/                  # 4 个平台中立 skill（brief/engine/audio/deliver）
├── agents/                  # 2 个专家 agent（motion-director / motion-auditor）
├── hooks/                   # 2 个硬门（commit 前审计拦截 / 无探针渲染提醒）+ 豁免说明
├── scripts/audit/           # 28 条确定性自查规则（零第三方依赖）
├── fixtures/                # 冒烟测试用例（坏/好对照）
├── smoke_test.py            # 一键冒烟测试
├── ATTRIBUTION.md           # 灵感来源与许可声明
└── LICENSE                  # MIT
```

## 什么时候用 / 什么时候不用（FAQ）

**什么时候用：**

- 你要做产品宣传片/片头/转场，但不会 After Effects 也不想买订阅时 → 用 `/lhg-motion-video:motion-video`，一句话开工
- 你已经有片子，只想确认"导出的参数对不对、字幕安不安全"时 → 跑 `/lhg-motion-video:audit`
- 你要发布前怕翻车（iPhone 偏色、网页播等半天、字幕被平台 UI 遮挡）时 → 跑 `/lhg-motion-video:audit`
- 你想给团队立一套"成片必须过自检"的纪律时 → 它的 hook 硬门与审计脚本开箱即用

**什么时候不用：**

- 你剪的是实拍口播/剧情/混剪 → 那是 `lhg-video-edit` 的地盘，本插件是"代码生成动效"专家
- 你要的是 AI 生成式视频（文生视频/图生视频）→ 本插件是程序化渲染管线，不做生成式模型
- 你的片子强依赖 After Effects 特效插件 → 本插件路线是纯代码，插件生态不在此列

**风险点诚实说明：**

- **渲染耗时**：全量渲染按"帧数×单帧耗时"计，动手前插件会先报预估；想快就用探针低分辨率先看构图
- **浏览器依赖**：逐帧渲染需要无头浏览器环境，首次使用要装浏览器（插件会指引，一次搞定）
- **版权音乐**：BGM 三选一——自制 / 已购版权 / 免费曲库；"网上下载的热歌"不算来源，审计会标 warning
- **画面真实性**：审计查的是格式与一致性，查不出"数据是编的"；示意数据必须标注，这是人工评审的红线

## lhg-plugs 插件矩阵

| 插件 | 一句话 | 安装 |
|---|---|---|
| [lhg-motion-video](https://github.com/lhg-plugs/lhg-motion-video) | 动效视频专家：需求→导演brief→纯代码渲染→成片导出 | `/plugin install lhg-motion-video@lhg-plugs` |
| [lhg-fullstack](https://github.com/lhg-plugs/lhg-fullstack) | 小白一句话 → 高质量全栈应用 | `/plugin install lhg-fullstack@lhg-plugs` |

## 自检与反馈

本插件自带质检：每次使用后可跑 `python3 smoke_test.py` 一键验证（JSON 合法、skill/command/agent 完整性、28 条规则、fixtures 命中、hooks 行为）。

发现 bug 或有改进建议，以 `[QC] <一句话问题>` 为标题提交到 https://github.com/lhg-plugs/lhg-motion-video/issues，正文写清"复现步骤 → 实际表现 → 期望表现"。

## 出品：刘洪光

本插件由真人出镜 IP「刘洪光」（安徽合肥）出品，归属 [lhg-skills](https://github.com/lhg-skills)。

- GitHub 主页：https://github.com/lhg-skills —— 全部 skill 开源在此，欢迎 star
- 抖音：搜「刘老师讲AI实战」
- 微信：lhgsmsw
