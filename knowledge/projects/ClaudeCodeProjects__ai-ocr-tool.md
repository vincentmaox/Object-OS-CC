# ai-ocr-tool

- registry_key: ClaudeCodeProjects__ai-ocr-tool
- path: D:\ClaudeCodeProjects\ai-ocr-tool
- status: 停滞
- mva: All-in @ 2026-09-18T09:09:22.955380900+08:00
- tech: Node.js, React
- scripts: dev=concurrently -k "vite --host 127.0.0.1" "wait-on tcp:5173 && cross-env VITE_DEV_SERVER_URL=http://127.0.0.1:5173 electron ."; build=npm run typecheck && vite build && tsc -p tsconfig.main.json; typecheck=npx tsc --noEmit && npx tsc -p tsconfig.main.json --noEmit && npx tsc -p tsconfig.test.json --noEmit; package=npm run build && node scripts/canvas-alias.mjs && node scripts/bundle-vcredist.mjs && cross-env CSC_IDENTITY_AUTO_DISCOVERY=false ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/ ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/ electron-builder --win portable; test=vitest run; postinstall=node scripts/canvas-alias.mjs; download-ocr-models=node scripts/download-ocr-models.mjs; typecheck:renderer=npx tsc --noEmit
- tech_needs: 部署配置缺失
- git: main, clean
- last_commit: 1e1efb00 2026-09-19 docs: quick progress index in PROJECT_LOG + update CLAUDE.md status to v0.4.4
- activity: last_code_edit 2026-09-18 (23.3d), files 193
- docs: readme✓ claude_md✓ docs_dir✓

## blockers
- [low] tech_need: 部署配置缺失
- [low] stale: 项目已停滞 22 天

_自动更新: 2026-10-11T18:06:44_

<!-- MANUAL -->
