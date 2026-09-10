# docreview-ai

- registry_key: ClaudeCodeProjects__docreview-ai
- path: D:\ClaudeCodeProjects\docreview-ai
- status: 卡点
- mva: Watch @ 2026-06-17T17:17:31.546775900+08:00
- tech: Node.js, React, Tailwind
- scripts: dev=vite; build=tsc && vite build; preview=vite preview; electron:dev=concurrently "vite" "wait-on http://localhost:5173 && electron ."; electron:build=vite build && electron-builder
- tech_needs: npm install（缺少node_modules）, 配置.env文件（有.example模板）, 部署配置缺失
- git: v0.2-rewrite, clean
- last_commit: 9cc15575 2026-07-20 feat: update model clients + add RCC-M test docs
- activity: last_code_edit 2026-06-10 (90.9d), files 139
- docs: readme✗ claude_md✓ docs_dir✓

## blockers
- [medium] git_unpushed: 有 1 个提交未推送
- [medium] missing_doc: 缺少 README.md
- [low] tech_need: npm install（缺少node_modules）
- [high] tech_need: 配置.env文件（有.example模板）
- [low] tech_need: 部署配置缺失
- [low] stale: 项目已停滞 51 天

## todos
- CLAUDE.md:47 - [ ] **P1** 数据层（sql.js + schema + 迁移 + 设置 KV）
- CLAUDE.md:48 - [ ] **P2** 模型层（4 端点 OpenAI-compatible 客户端 + 测试）
- CLAUDE.md:49 - [ ] **P3** 知识库（CRUD + 文档导入 + 切片 + 向量化）
- CLAUDE.md:50 - [ ] **P4** 混合检索（向量 + LIKE/FTS5 + Reranker 降级 + 引用）
- CLAUDE.md:51 - [ ] **P5** 审查引擎（编排 + 哨兵协议 + 严重度 + 保守回答）

_自动更新: 2026-09-09T09:43:21_

<!-- MANUAL -->
