# NuclearPowerAI

- registry_key: ClaudeCodeProjects__NuclearPowerAI
- path: D:\ClaudeCodeProjects\NuclearPowerAI
- status: All-in (manual: All-in)
- mva: All-in @ 2026-07-30T11:06:02.131742100+08:00
- tech: Node.js, React
- scripts: dev=concurrently -k "vite --host 127.0.0.1" "wait-on tcp:5173 && cross-env VITE_DEV_SERVER_URL=http://127.0.0.1:5173 electron ."; build=npm run typecheck && vite build && tsc -p tsconfig.main.json; typecheck=tsc --noEmit && tsc -p tsconfig.main.json --noEmit && tsc -p tsconfig.test.json --noEmit; package=npm run build && node scripts/canvas-alias.mjs && node scripts/bundle-vcredist.mjs && cross-env CSC_IDENTITY_AUTO_DISCOVERY=false electron-builder --win portable; test=vitest run; postinstall=node scripts/canvas-alias.mjs; download-ocr-models=node scripts/download-ocr-models.mjs
- tech_needs: 部署配置缺失
- git: feature/v0.19-multi-db, 11 uncommitted
- last_commit: 79d874a1 2026-10-10 feat(v0.31): PPT 工程模式（Kimi 工作流内网复刻）——create/edit/preview/export 工具组 + previewPpt
- activity: last_code_edit 2026-10-10 (1.1d), files 2061
- docs: readme✓ claude_md✓ docs_dir✓

## blockers
- [high] git_dirty: 有 11 个未提交更改（分支: feature/v0.19-multi-db）
- [low] tech_need: 部署配置缺失

## todos
- CLAUDE.md:299 - **长文双形态落盘**：`markdownToDocxSections()` 解析 ##/表格/列表 → `buildDocxBuffer(title, sections, {subtitle, toc: true, reference

_自动更新: 2026-10-11T18:06:44_

<!-- MANUAL -->
