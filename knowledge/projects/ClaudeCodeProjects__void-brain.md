# void-brain

- registry_key: ClaudeCodeProjects__void-brain
- path: D:\ClaudeCodeProjects\void-brain
- status: 活跃
- mva: All-in @ 2026-06-17T17:16:58.870965100+08:00
- tech: Node.js, React
- scripts: dev=concurrently -k "vite --host 127.0.0.1" "wait-on tcp:5173 && cross-env VITE_DEV_SERVER_URL=http://127.0.0.1:5173 electron ."; build=npm run typecheck && vite build && tsc -p tsconfig.main.json; typecheck=tsc --noEmit && tsc -p tsconfig.main.json --noEmit && tsc -p tsconfig.test.json --noEmit; package=npm run build && node scripts/canvas-alias.mjs && node scripts/patch-portable-nsi.mjs && node scripts/bundle-vcredist.mjs && cross-env CSC_IDENTITY_AUTO_DISCOVERY=false electron-builder --win portable; test=vitest run; postinstall=node scripts/canvas-alias.mjs; download-ocr-models=node scripts/download-ocr-models.mjs
- tech_needs: 部署配置缺失
- git: feature/kg-rag, clean
- last_commit: 9eb1c5d2 2026-08-27 fix: 测试 import 补 .js 扩展名适配 NodeNext 解析
- activity: last_code_edit 2026-08-27 (12.7d), files 6199
- docs: readme✓ claude_md✓ docs_dir✓

## blockers
- [medium] git_unpushed: 有 8 个提交未推送
- [low] tech_need: 部署配置缺失

_自动更新: 2026-09-09T09:43:21_

<!-- MANUAL -->
