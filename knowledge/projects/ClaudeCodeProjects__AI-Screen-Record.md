# AI-Screen-Record

- registry_key: ClaudeCodeProjects__AI-Screen-Record
- path: D:\ClaudeCodeProjects\AI-Screen-Record
- status: 停滞
- mva: All-in @ 2026-06-15T10:26:33.744811
- tech: Node.js, React, Tailwind
- scripts: dev=concurrently -k "vite --host 127.0.0.1" "wait-on tcp:5173 && cross-env VITE_DEV_SERVER_URL=http://127.0.0.1:5173 electron ."; build=vite build && esbuild src/main/index.ts --bundle --platform=node --outdir=dist/main --format=cjs --external:electron --external:uuid && esbuild src/preload/index.ts --bundle --platform=node --outdir=dist/preload --format=cjs --external:electron; typecheck=tsc --noEmit && tsc -p tsconfig.main.json --noEmit && tsc -p tsconfig.preload.json --noEmit; package=npm run build && cross-env CSC_IDENTITY_AUTO_DISCOVERY=false electron-builder --win portable; download-sidecars=node scripts/download-ffmpeg.mjs && node scripts/download-whisper.mjs; download-models=node scripts/download-models.mjs
- tech_needs: npm install（缺少node_modules）, 部署配置缺失
- git: main, clean
- last_commit: d5d424a8 2026-06-12 fix: show recording state immediately on start
- activity: last_code_edit 2026-06-12 (88.9d), files 213
- docs: readme✓ claude_md✓ docs_dir✓

## blockers
- [low] tech_need: npm install（缺少node_modules）
- [low] tech_need: 部署配置缺失
- [low] stale: 项目已停滞 89 天

_自动更新: 2026-09-09T09:43:21_

<!-- MANUAL -->
