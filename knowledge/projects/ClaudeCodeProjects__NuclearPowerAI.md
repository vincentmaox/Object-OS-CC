# NuclearPowerAI

- registry_key: ClaudeCodeProjects__NuclearPowerAI
- path: D:\ClaudeCodeProjects\NuclearPowerAI
- status: All-in (manual: All-in)
- mva: All-in @ 2026-07-30T11:06:02.131742100+08:00
- tech: Node.js, React
- scripts: dev=concurrently -k "vite --host 127.0.0.1" "wait-on tcp:5173 && cross-env VITE_DEV_SERVER_URL=http://127.0.0.1:5173 electron ."; build=npm run typecheck && vite build && tsc -p tsconfig.main.json; typecheck=tsc --noEmit && tsc -p tsconfig.main.json --noEmit && tsc -p tsconfig.test.json --noEmit; package=npm run build && node scripts/canvas-alias.mjs && node scripts/bundle-vcredist.mjs && cross-env CSC_IDENTITY_AUTO_DISCOVERY=false electron-builder --win portable; test=vitest run; postinstall=node scripts/canvas-alias.mjs; download-ocr-models=node scripts/download-ocr-models.mjs
- tech_needs: 部署配置缺失
- git: feature/multi-discipline-kb, 3 uncommitted
- last_commit: 818c6532 2026-08-25 docs: 技术方案与开发历程交流文档（v0.1-v0.11 完整演进 + 核心方案 + 踩坑清单）
- activity: last_code_edit 2026-08-25 (14.9d), files 615
- docs: readme✓ claude_md✓ docs_dir✓

## blockers
- [high] git_dirty: 有 3 个未提交更改（分支: feature/multi-discipline-kb）
- [low] tech_need: 部署配置缺失

_自动更新: 2026-09-09T09:43:21_

<!-- MANUAL -->
