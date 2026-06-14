# 思考池 — Inbox

> 你随手发的"想法/思考"都先进这里。等周一巡检决断。

## 格式约定

每条一行，格式：

```
[YYYY-MM-DDTHH:MM:SS] [项目名] 原文
```

例：

```
[2026-06-07T21:30:15] [docreview-ai] 想给审查报告加历史时间轴
```

## 流程

1. **Bot 接收** "我有个想法 / 思考" → 反问确认项目 → 写入本文件
2. **每周一 09:07** `thought_inspector.py` 自动巡检 → 推飞书卡片
3. **你决断** → 移到 `active.md` / `watching.md` / `killed.md`

## 清单（按时间倒序）

# 思考池 — Inbox

> 你随手发的"想法/思考"都先进这里。等周一巡检决断。

## 格式约定

每条一行，格式：

```
[YYYY-MM-DDTHH:MM:SS] [项目名] 原文
```

例：

```
[2026-06-07T21:30:15] [docreview-ai] 想给审查报告加历史时间轴
```

## 流程

1. **Bot 接收** "我有个想法 / 思考" → 反问确认项目 → 写入本文件
2. **每周一 09:07** `thought_inspector.py` 自动巡检 → 推飞书卡片
3. **你决断** → 移到 `active.md` / `watching.md` / `killed.md`

## 清单（按时间倒序）

<!-- BOT_APPEND_BELOW_THIS_LINE -->
[2026-06-14T21:00:00] [voidarchitect-site] 工作室主页 v2 启动：Astro 5 + R3F WebGL 流体 Hero + Tailwind + Framer Motion。沿用旧 Vercel 项目（disconnect voidcompass → connect 新仓），DNS/Cloudflare 不动。三频 4/4/5=13/15 All-in。72h MVA 起始 2026-06-15：D1 静态架构+数据管道 D2 第一版上线给3个朋友看 D3 跨仓 webhook+自动部署。数据源：ProjectOS 加 export_public_registry.py 只导出公开字段（name/stage/freq_total/freq_suggestion/last_action摘要/github链接）→ data/public-registry.json 入 git → 构建期 fetch。
[2026-06-14T20:30:00] [void-charter-bos-v1] 老赫读完《茧房破壁操作系统 v1.0》：BOS = ProjectOS 的线下采样插件而非新系统。第11.2章三频共振检查 ≈ 已落的 freq_resonance；第26.2章探路先遣队训练数据 = 认错套利结构化模板。决议：30天内不为BOS落码（registry/breaching_log/killed.md都不动），等老茅真去华强北/五金店蹲过一次再说。详 memory/bos-charter-v1-read.md
[2026-06-14T20:00:00] [void-charter-12-blueprints] 来自《虚空建筑师野化宣言 v1.0》第八部分 12 方案：以下 11 条种子入池（方案 1=docreview-ai 已落地不重复），三频分由原文给定，MVA 起始日按分数高低错峰排进周一思考池巡检；MVA 起始日 ≤ 今日的，会被 thought_inspector 标记为「待决断」推卡片
[2026-06-14T20:00:01] [void-blueprint-03-prompt-market] 方案3：Prompt Engineering 工作流市场（Next.js+Stripe+静态内容）。三频 5/4/5=14/15 → All-in。MVA 起始 2026-06-15（高分先发）
[2026-06-14T20:00:02] [void-blueprint-12-freq-calc] 方案12：频域决策计算器 SaaS（React+D3.js）。强差异化（即老茅核心方法论产品化）。三频未给分，初判 5/4/5=14/15 → All-in 候选。MVA 起始 2026-06-15
[2026-06-14T20:00:03] [void-blueprint-02-mbti-house] 方案2：MBTI 分院帽（虚空建筑师学院产品化，VoidCompass 落地）。三频 5/3/5=13/15 → All-in。MVA 起始 2026-06-16
[2026-06-14T20:00:04] [void-blueprint-04-72h-template] 方案4：AI 原生开发日志模板（Notion/Obsidian），$29-49 一次性。MVA 起始 2026-06-17（轻量低维护）
[2026-06-14T20:00:05] [void-blueprint-07-wild-newsletter] 方案7：「虚空建筑师野化日志」付费 newsletter（$5/月或$50/年）。内容即产品。MVA 起始 2026-06-18
[2026-06-14T20:00:06] [void-blueprint-11-failure-archive] 方案11：独立开发者失败案例库（$19/次或$49/年）。差异化「失败学」，与老茅 10% 观测正反馈协议一致。MVA 起始 2026-06-19
[2026-06-14T20:00:07] [void-blueprint-10-arbitrage-intel] 方案10：AI 工具套利情报站（$9/月，每周 PDF）。MVA 起始 2026-06-20
[2026-06-14T20:00:08] [void-blueprint-09-nuclear-consulting] 方案9：核电+AI 跨界咨询（$200-500/小时或$5000-20000/项目）。高客单价。MVA 起始 2026-06-21
[2026-06-14T20:00:09] [void-blueprint-05-cross-border-ai] 方案5：跨境电商 AI 工具包（Streamlit+Claude API，$19/月或按次）。三频 4/4/4=12/15 → 需要更多验证。MVA 起始 2026-06-22
[2026-06-14T20:00:10] [void-blueprint-06-ai-child] 方案6：AI 子女/电子宠物框架（多平台 Bot+Claude API）。三频 5/3/4=12/15 → Watch。MVA 起始 2026-06-23
[2026-06-14T20:00:11] [void-blueprint-08-claude-code-course] 方案8：Claude Code 实战视频课程（$99-199 或 $19/月）。需要先有可拍摄素材，建议作为前述 SaaS 的副产品。MVA 起始 2026-06-24
[2026-06-14T20:00:12] [docreview-ai] 方案1（AI 文档审查智能体，三频 5/4/5=14/15）= 已落地的 docreview-ai 项目本身，不重复入池；建议给该项目补三频评分锁定 All-in 决断
[2026-06-08T15:00:00] [upwork-bidder] Upwork投标自动化：拉取标的→筛选→生成投标方案→快速投出，同时自动做出项目方案
[2026-06-08T14:30:00] [_ProjectOS] 项目评估功能：对各个项目进行评估+改善建议，每日回顾工作表现夸一下开发的AI和自己
[2026-06-07T22:54:55] [docreview-ai] 便携版任务栏图标与 NPAI 相同，需换独立图标避免混淆
