# hermes-desktop

- registry_key: ClaudeCodeProjects__hermes-desktop
- path: D:\ClaudeCodeProjects\hermes-desktop
- status: 进行中
- mva: All-in @ 2026-06-17T14:59:39.922740800+08:00
- tech: Node.js, React, Tailwind
- scripts: dev=vite; build=tsc && vite build; preview=vite preview; tauri=node scripts/tauri.mjs
- tech_needs: 部署配置缺失
- git: main, 14 uncommitted
- last_commit: 9df30c61 2026-07-25 docs: CLAUDE.md TODO 标记 v0.5.4 完成 (最近活动徽章+新建项目+立即扫描)
- activity: last_code_edit 2026-09-08 (0.4d), files 592
- docs: readme✓ claude_md✓ docs_dir✓

## blockers
- [medium] git_dirty: 有 14 个未提交更改（分支: main）
- [low] tech_need: 部署配置缺失

## todos
- CLAUDE.md:75 ## TODO（按优先级）
- CLAUDE.md:98 ## TODO（下一步候选，按优先级）
- CLAUDE.md:100 - [ ] **TTS 音色调优** - 换 MiniMax voice_id（female-chengshu 成熟 / male-qingxue 男声等），或用音色复刻克隆老茅指定音色
- CLAUDE.md:101 - [ ] **VAD 阈值调整** - 300ms discard 窗口 + silero VAD `min_silence_duration=0.7s` 可调，实测老茅反馈丢字严重时调到 150ms；SettingsPanel UI 暴
- CLAUDE.md:102 - [ ] **流式 LLM + 流式 TTS** - 目前 sidecar 等 LLM 整段 AssistantMessage 才切句发 text_chunk，可改 stream LLM token 边收边切句

_自动更新: 2026-09-09T09:43:21_

<!-- MANUAL -->
