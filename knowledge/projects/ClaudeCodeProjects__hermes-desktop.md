# hermes-desktop

- registry_key: ClaudeCodeProjects__hermes-desktop
- path: D:\ClaudeCodeProjects\hermes-desktop
- status: 卡点
- mva: All-in @ 2026-06-17T14:59:39.922740800+08:00
- tech: Node.js, React, Tailwind
- scripts: dev=vite; build=tsc && vite build; preview=vite preview; tauri=node scripts/tauri.mjs
- tech_needs: 部署配置缺失
- git: main, 1 uncommitted
- last_commit: b05f66a9 2026-09-15 fix: v0.7.9 强制子会话保存 Claude transcript
- activity: last_code_edit 2026-09-15 (26.2d), files 3085
- docs: readme✓ claude_md✓ docs_dir✓

## blockers
- [high] git_dirty: 有 1 个未提交更改（分支: main）
- [low] tech_need: 部署配置缺失

## todos
- CLAUDE.md:79 ## TODO（按优先级）
- CLAUDE.md:116 ## TODO（下一步候选，按优先级）
- CLAUDE.md:118 - [ ] **TTS 音色调优** - 换 MiniMax voice_id（female-chengshu 成熟 / male-qingxue 男声等），或用音色复刻克隆老茅指定音色
- CLAUDE.md:119 - [ ] **流式 LLM + 流式 TTS** - 目前 sidecar 等 LLM 整段 AssistantMessage 才切句发 text_chunk，可改 stream LLM token 边收边切句
- CLAUDE.md:120 - [ ] **火山 S2S-SC 真全双工双通道** - 文字走 Claude + MiniMax，语音走 S2S-SC（需要火山引擎 App ID + Access Token，老赫人格要重灌 system prompt）

_自动更新: 2026-10-11T18:06:44_

<!-- MANUAL -->
