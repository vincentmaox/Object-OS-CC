# AI-Screen-Record

- registry_key: ClaudeCodeProjects__AI-Screen-Record
- path: D:\ClaudeCodeProjects\AI-Screen-Record
- status: 卡点
- mva: All-in @ 2026-06-15T10:26:33.744811
- tech: Node.js, React, Tailwind
- scripts: dev=concurrently -k "vite --host 127.0.0.1" "wait-on tcp:5173 && cross-env VITE_DEV_SERVER_URL=http://127.0.0.1:5173 electron ."; build=vite build && esbuild src/main/index.ts --bundle --platform=node --outdir=dist/main --format=cjs --external:electron --external:uuid && esbuild src/preload/index.ts --bundle --platform=node --outdir=dist/preload --format=cjs --external:electron; typecheck=tsc --noEmit && tsc -p tsconfig.main.json --noEmit && tsc -p tsconfig.preload.json --noEmit; test=vitest run; test:watch=vitest; test:e2e=vitest run --config vitest.e2e.config.ts e2e.test; verify=npm run typecheck && npm run test && npm run build; package=npm run build && cross-env CSC_IDENTITY_AUTO_DISCOVERY=false electron-builder --win portable; download-sidecars=node scripts/download-ffmpeg.mjs && node scripts/download-whisper.mjs; download-models=node scripts/download-models.mjs; e2e:pipeline=vitest run --config vitest.e2e.config.ts pipeline.e2e
- tech_needs: 部署配置缺失
- git: main, 1 uncommitted
- last_commit: 5c5d2203 2026-09-27 fix: redirect Chromium userData to portable dir (three-zeros compliance)
- activity: last_code_edit 2026-09-27 (14.1d), files 545
- docs: readme✓ claude_md✓ docs_dir✓

## blockers
- [high] git_dirty: 有 1 个未提交更改（分支: main）
- [medium] git_unpushed: 有 4 个提交未推送
- [low] tech_need: 部署配置缺失

_自动更新: 2026-10-11T18:06:44_

<!-- MANUAL -->
