# void-brain

- registry_key: ClaudeCodeProjects__void-brain
- path: D:\ClaudeCodeProjects\void-brain
- status: 卡点
- mva: All-in @ 2026-06-17T17:16:58.870965100+08:00
- tech: Node.js, React
- scripts: dev=concurrently -k "vite --host 127.0.0.1" "wait-on tcp:5173 && cross-env VITE_DEV_SERVER_URL=http://127.0.0.1:5173 electron ."; build=npm run typecheck && vite build && tsc -p tsconfig.main.json; typecheck=tsc --noEmit && tsc -p tsconfig.main.json --noEmit && tsc -p tsconfig.test.json --noEmit; package=npm run build && node scripts/canvas-alias.mjs && node scripts/patch-portable-nsi.mjs && node scripts/bundle-vcredist.mjs && cross-env CSC_IDENTITY_AUTO_DISCOVERY=false electron-builder --win portable; test=vitest run; postinstall=node scripts/canvas-alias.mjs; download-ocr-models=node scripts/download-ocr-models.mjs
- tech_needs: 部署配置缺失
- git: feature/v0.9-eval, 5 uncommitted
- last_commit: 8e5b64f9 2026-09-17 docs: v0.7 经验层验收记录 + v0.9 评估基座与首条基线记录
- activity: last_code_edit 2026-09-17 (24.7d), files 6696
- docs: readme✓ claude_md✓ docs_dir✓

## blockers
- [high] git_dirty: 有 5 个未提交更改（分支: feature/v0.9-eval）
- [low] tech_need: 部署配置缺失

_自动更新: 2026-10-11T18:06:44_

<!-- MANUAL -->
