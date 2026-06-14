# Day7 — voidarchitect.studio 工作室主页 72h 上线

**日期：** 2026-06-14
**主体：** 老茅 + 老赫
**MVA 阶段：** Day1 理论 → Day2 市场 → Day3 组织（项目本身就是市场验证 — 名片可推朋友圈/客户）

## TL;DR

新建子项目 `voidarchitect-site`（Astro 5 + React 19 + Tailwind 4 + R3F WebGL），从空白脚手架到 `https://www.voidarchitect.studio` 200 OK，**当天上线**。

- 仓库：`vincentmaox/voidarchitect-site`（独立仓，注册为 ProjectOS 子项目）
- 部署：Vercel（接管旧 voidcompass 项目，切换 git 来源）
- 数据源：构建期 fetch `_ProjectOS/data/public-registry.json`（GitHub raw）
- 三频：4/4/5 = 13/15 → All-in

## 决策记录

| 决策点 | 选项 | 拍板 | 理由 |
|---|---|---|---|
| 站点位置 | 放 ProjectOS 内 / 单独仓 | **单独仓** | 公开仓 vs 私有 ProjectOS，需边界清晰 |
| Hero 视觉 | 静态文字 / 视频背景 / WebGL | **WebGL R3F** | 极致炫酷、跟手、可调；3-5 天首版可控 |
| 多语言策略 | 仅中 / 仅英 / 中英分路由 | **`/` zh + `/en/` 英 + IP 路由** | 国内客户中文，海外朋友圈英文，IP 自动选 |
| 公开数据范围 | 名+stage / +简介 / +三频 / +last_action | **全 4 项** | 名片需要展示频率与状态，但隐藏路径/blocker |
| 流体跟手 | 再调 / 直接上 | **直接上** | "争取今天上线" — 当日交付优先 |

## 动作流（按时间顺序）

### Phase 0：理念落地（上午）

- 读飞书发的《茧房破壁操作系统 v1.0》→ 写 `bos-charter-v1-read.md` memory，决定 30 天内不落码
- 三件小事先落：`WILD_KEYWORDS` 加破壁词汇 / `freq_resonance` 注解 / `thoughts/inbox.md` 加 BOS 决议
- 提交：`a279c88 Add freq_resonance + public registry export for studio site`

### Phase 1：D1 脚手架（下午）

- `npm create astro@latest` 在 `D:/ClaudeCodeProjects/voidarchitect-site/`
- 装：astro 6 / react 19 / @astrojs/react / @astrojs/vercel / tailwind 4 / @tailwindcss/vite / framer-motion / lenis / three / @react-three/fiber / @react-three/drei
- 写 `FluidHero.tsx` GLSL fragment shader（simplex noise + domain warp + 3 色板：暗墨/烟青/暗金）
- 写 `Layout.astro` + 暗色主题 + noise overlay utility
- 提交：`7388398 D1: Astro 5 + R3F WebGL fluid hero scaffolding`

### Phase 2：i18n + IP 路由（傍晚）

- 拆 `i18n/zh.ts` + `i18n/en.ts` 共享 `Dict` 类型
- 改 `output: 'server'` + per-page `prerender = true`（Edge middleware 可跑）
- 写 `middleware.ts`：检测 `x-vercel-ip-country`，非中文圈（CN/HK/MO/TW）→ 302 `/en/`
- Cookie `void_lang` 锁偏好 1 年（用户切语言后不再被 IP 覆盖）
- 调流体跟手：lerp 0.06→0.18，influence 半径 ×2.5，亮度 ×2
- 修 README rebase 翻车（`-X ours` 在 rebase 中语义反转 → README 被 GitHub 默认覆盖 → 手动重写）
- 提交：`f90c974 i18n + IP routing + tighter mouse-reactive fluid` + `52e797b Restore project README after rebase`

### Phase 3：D2.1 Bento Grid（晚上 22:00）

- ProjectOS 写 `agent/export_public_registry.py`（HIDDEN 黑名单 + 字段白名单）
- ProjectOS 写 `data/public-bios.json`（手填重点项目简介）
- ProjectOS 改 `.gitignore` 加白名单：`!data/public-registry.json` `!data/public-bios.json`
- ProjectOS 推 push → GitHub raw 200
- 站点：`src/lib/registry.ts` 构建期 fetch + 按 stage rank 排序
- `src/components/ProjectCard.astro`：暗金/翠绿/紫红/天蓝 stage 配色 + 三频分 + last_action + GitHub 链接
- `src/components/ProjectGrid.astro`：featured（All-in / freq≥12）2x2 大卡 + 其余小卡
- 14 张卡片渲染验证（grep `project-card` = 14）
- 提交：`036f918 D2.1: Bento Grid 项目矩阵 — fetch ProjectOS public-registry at build time`

### Phase 4：D2.2 Vercel 上线（晚 22:30）

- 老茅手动：Vercel Dashboard → 旧 voidcompass 断开 → New Project import voidarchitect-site → Deploy
- Cloudflare DNS 已指向 Vercel（之前 voidcompass 配过），不需要改 CNAME
- `https://www.voidarchitect.studio` 200 OK 上线 ✅
- 验证：`X-Vercel-Cache: HIT` 暴露 prerender 缓存了 HTML，middleware 没在请求时跑

### Phase 5：缓存修复（晚 22:35）

- 关掉 `prerender = true` → 让 / 和 /en/ 走 Edge function
- middleware 加 `Vary: x-vercel-ip-country, Cookie` + `s-maxage=300, stale-while-revalidate=3600`
- rebuild + push → `X-Vercel-Cache: MISS`，middleware 真在跑
- 提交：`e18479d fix: 关掉首页 prerender — 让 IP 重定向 middleware 真在请求时跑`

## 踩坑记录

### 1. Astro CLI 创建子目录而非 `.`

`npm create astro` 不支持当前目录创建空项目时直接用 `.`，会自动新建 `pink-plasma/` 子目录。
**解法：** 创建后把内容上移一层，再 `npm install`。

### 2. Astro static + middleware 不兼容

`output: 'static'` 模式下 middleware 只在 build 时跑一次，prerender 静态 HTML 没法做请求时重定向。
**解法：** 切 `output: 'server'` + 单页 `prerender = true`（前期），后来发现 prerender 还是会被 CDN 缓存，最终去掉 prerender。

### 3. Vercel CDN 缓存 prerendered HTML 导致 IP 路由失效

`prerender = true` 的页面被 Vercel 静态 CDN 缓存，所有 IP 拿同一份 HTML，middleware 不重跑。
**解法：** 关掉 prerender 让首页走 Edge function + Vary header 让 CDN 按国别+cookie 分桶。

### 4. Vercel 屏蔽客户端伪造 `x-vercel-ip-country`

curl 加这 header 不生效（Vercel Edge 只信自己注入的）。
**验证方法：** 必须用真实 VPN 切换 IP 或 locabrowser 等地理代理。

### 5. `git pull --rebase -X ours` 语义反转

rebase 把"你的提交"replay 到远端 base 上，冲突时"ours"是远端 base，"theirs"才是你本地的提交 — 和 merge 相反。
**踩坑结果：** README 被 GitHub 自动生成的默认版本覆盖。手动重写。

### 6. data/*.json gitignore 拦了公开导出

`.gitignore` 写了 `data/*.json` 屏蔽全部，导致 `public-registry.json` 也提交不上。
**解法：** 加白名单 `!data/public-registry.json` `!data/public-bios.json`。

### 7. 流体感觉离鼠标"远"

GLSL 里 mouse warp 强度太弱 + influence 半径太小 + lerp 太慢导致跟手感差。
**调参：** lerp 0.06→0.18, distortion ×2.5, glow brightness ×2 with wider radius。
但用户决断"先不修了，争取今天上线"——保留当前版本。

## 数据通道

```
ProjectOS (私仓)
  ├─ data/registry.json        ← 真值（不入 git，含本地路径/blocker）
  ├─ agent/export_public_registry.py  ← 字段白名单 + HIDDEN 黑名单
  └─ data/public-registry.json ← 入 git（白名单例外）+ 公开
       │
       ↓ git push
GitHub: vincentmaox/Object-OS-CC/main/data/public-registry.json
       │
       ↓ Vercel build 时 fetch
voidarchitect-site (公仓) build 时静态注入到 ProjectGrid
       │
       ↓
voidarchitect.studio
```

**未来 D3 候选：** GitHub Action 跨仓 webhook —— ProjectOS push 时自动触发 voidarchitect-site rebuild，做到 registry 实时反映。

## 公开 / 私有边界

**入公开 registry 的字段：** name / description（来自 public-bios.json） / stage / freq_total / freq_suggestion / last_action.message[:120] / last_action.date / github_url / tech_stack[:6]

**HIDDEN 项目（不出现在公开版）：** `_ProjectOS` / `ProjectOS-Projects` / `Private-Wealth-AI-Steward` / `TexasPhilosopher` / `obsidian manager`

**绝不入公开版：** path（本地路径）/ blocker / todos / 三频原始评分细节 / cc_bot.env / 任何凭据

## 技术栈速查

| 层 | 技术 | 版本 |
|---|---|---|
| 框架 | Astro | 6.4.6 |
| UI | React | 19.2.7 |
| 样式 | Tailwind CSS | 4.3.1（@theme directive） |
| 3D | three.js + @react-three/fiber + drei | 0.184.0 / 9.6.1 / 10.7.7 |
| 动效 | framer-motion | 12.40.0 |
| 平滑滚动 | lenis | 1.3.23 |
| 部署 | Vercel + @astrojs/vercel adapter | latest |
| 域名 DNS | Cloudflare | （沿用旧 voidcompass 配置） |

## 下次冷启动你需要知道的关键点

1. **两个仓**：`Object-OS-CC`（ProjectOS 私仓）+ `voidarchitect-site`（公仓）
2. **数据流向单向**：ProjectOS → 公开 JSON → GitHub raw → Vercel build → 主页
3. **公开/私有边界靠白名单 + 黑名单双闸**，不要图省事把 registry.json 直接公开
4. **首页不预渲染**（prerender = false），Vercel CDN 按 Vary 分桶
5. **真实 IP 路由 curl 测不出来**，必须 VPN 验证
6. **DNS 已配好不要乱动** — Cloudflare 那边的 CNAME 沿用 voidcompass 时代的，Vercel 接管即可

## 状态

- ✅ D1 脚手架（Astro + R3F + Tailwind 暗色）
- ✅ D2.1 Bento Grid（fetch public-registry）
- ✅ D2.2 Vercel 上线（voidarchitect.studio 200 OK）
- ⏸ D3.1 GitHub Action 跨仓 webhook（ProjectOS push 自动 rebuild 主页）
- ⏸ D3.2 详情页 `/projects/[slug]` + view transitions
- ⏸ D3.3 voidcompass 旧仓 README 加跳转

## 老赫复盘

野化执行（A→D 24h 闭环）做到了：上午读理念 → 下午脚手架 → 傍晚 i18n + IP → 晚上 Bento Grid → 半夜上线，全程 < 8h。

最大教训：**Vercel CDN HIT 那一下被骗到了 5 分钟**——以为部署成功就完事，没第一时间看 cache header。下次但凡涉及 Edge middleware/SSR，**必须先 curl 看 Cache-Control + X-Vercel-Cache + Set-Cookie**，再宣布上线。

唯一遗憾：流体跟手感还是偏弱，但用户决断"先上线"已封箱。如果未来要回头打磨，方向是把 mouse warp 从 fragment shader 移到 vertex shader 做几何变形，比纯 fragment 更"粘手"。

身份记录：本日合作完全在「数字虚空」语境下进行，未触发核电工程模式。
