# Day8 — 跨仓 webhook + 每日 auto-commit + 站点大片感改版

**日期：** 2026-06-15
**主体：** 老茅 + 老赫

## 跨仓 webhook（D3.1 技术债清零）

**问题：** ProjectOS push public-registry.json 后，voidarchitect-site 不会自动 rebuild，主页数据永远滞后。

**解法：**
1. `.github/workflows/trigger-site-rebuild.yml` — GitHub Actions，监听 `data/public-*.json` 变更
2. 触发 Vercel Deploy Hook（secret: `VERCEL_DEPLOY_HOOK`）
3. Vercel 收到后自动 rebuild voidarchitect-site

**验证：** 改 `public-bios.json` → push → Actions run `completed/success` → Vercel rebuild → 站点内容更新（"Astro 6" + "实时展示在建工程矩阵" 验证通过）

**commit:** `34e25c1`（workflow）+ `7e9c324`（bio test）+ `9ef8e93`（re-export registry）

## 每日脚本加 auto-commit + push

**问题：** `daily_projectos_report.py` 每天 9:07 跑完后只写到本地文件，不 push，webhook 永远不会触发。

**解法：** `git_push_public_data()` 函数——检测 `data/public-*.json` 是否变更，有则 `git add + commit + push`。零人工。

**commit:** `588e596`（加入 export_public_registry）+ `c6b2e8c`（auto-commit 功能）

## 站点改版（在 voidarchitect-site 仓记录）

详见 `voidarchitect-site/docs/journal/2026-06-15-design-overhaul.md`

核心变化：
- D2.3 蓝青科技风过渡版 → D2.4 大片感终版
- #0D1117 + #00D4FF 电光青 + #FF6B35 炽热橙
- 渐变发光球 + 鼠标光晕 + 玻璃拟态卡片
- 无新依赖（纯 CSS/Tailwind + 已有 framer-motion）

## 朋友圈文案

`templates/voidarchitect-site-launch-promo.md` — 6 种变体（3 中文 + 3 英文），含截图/录屏建议。

## 状态

- ✅ 跨仓 webhook 全链路验证
- ✅ 每日 auto-commit + push
- ✅ 站点大片感改版上线
- ⏸ 朋友圈推送（待老茅发）
- ⏸ 真实客户反馈收集
