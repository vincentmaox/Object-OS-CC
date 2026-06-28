# FrequencyOS — ProjectOS 控制层

> 定位：**ProjectOS 的个人控制论层**。
>
> 把目标、行为、情绪、评价、时间重新统一为一个可采样、可滤波、可决策、可反馈的闭环系统。
>
> 不是又一个效率工具，不是打卡 App，不是 AI 聊天框。

---

## 一句话使命

让 ProjectOS 每天能回答一个问题：

> **老茅今天的行为，是否服从当前主频目标？**

不是"今天有什么任务"，而是"今天哪些行为真的服从了主频"。

---

## 五层架构（详见 `control_layer.md`）

```
L5  反馈层  Control Feedback   ← 五频报告 + 心力账户结算
L4  执行层  Action Protocol    ← 24h A→D 闭环 + 9 类最小动作
L3  决策层  Frequency Decision ← 三频评分 + 72h MVA + 六态
L2  滤波层  Noise Filter       ← 噪声/控制/主观三类干扰分流
L1  采样层  Reality Sampler    ← 五源信号采集
```

---

## V0.1（当前）— Markdown MVP

边界：不写 UI、不接屏幕监控、不接可穿戴、不做心理评估。

5 个核心文件：

| 文件 | 控制层 | 职责 |
|---|---|---|
| `goals.md` | L3 | 目标锁定协议 + 三频评分 + 90 天锁定期 |
| `daily_log.md` | L1+L5 | 每日频域采样 + 心力账户 |
| `anti_swing_inbox.md` | L2 | 摇摆冲动缓冲池 + 24h 冷却 + 72h 验证 |
| `weekly_report.md` | L5 | 周度频谱报告 + 组织度指数 |
| `prd.md` | 元 | 产品定义 + V0.2/V0.3/V1.0 演进路线 |
| `control_layer.md` | 元 | 五层架构 + 三份文档来源映射 |

辅助：

- `templates/` — goal_lock / daily_sample / anti_swing / weekly_report 四个空白模板
- `scripts/frequency_daily.py` — 独立采样合并入口（不依赖 ProjectOS 调度）

### V0.1 成功标准

**连续 30 天每日采样不中断，且组织度指数稳定 ≥ 70。**

---

## 运行协议

### 每日晨间校准（09:00 前完成）

1. 确认今日唯一主频
2. 写下今日主频咒语
3. 预设主频块时间
4. 明确高频噪音预算

### 日间摇摆拦截

出现"换方向 / 新项目 / 放弃 / 焦虑 / 新鲜感"时，**不直接行动**：

1. 写入 `anti_swing_inbox.md`
2. 判断类型：战略机会 / 高频噪音 / 情绪逃避 / 新鲜感渴求 / 身份焦虑
3. 默认进入 24h 冷却
4. 只有通过三频评分和 72h 微验证，才允许升级

### 晚间采样复盘（22:00 前完成）

写入 `daily_log.md`：

- 主频投入时间 + 具体产出
- 情绪评分 + 身体能量评分
- 高频噪音时间
- 目标摇摆事件
- SOP 遵守情况
- 心力账户净额
- 明日主频咒语

### 周度频谱报告（每周日 21:00）

由老赫生成草稿，老茅确认后定稿，写入 `weekly_report.md`。

---

## V0.2 — 调度集成（计划）

- `daily_recap.py`（22:57 晚报）末尾追加 FrequencyOS 当日采样段
- `thought_inspector.py`（周一 09:07）扫描 `anti_swing_inbox.md` 单独成段
- 飞书晨报卡片加「今日主频咒语」字段
- `frequency_daily.py` 接入自动 7 日均值计算

## V0.3 — 现实采样器雏形（计划）

把 Hermes Desktop 的语音入口接到 FrequencyOS：

- 语音冲动 → 自动写 `anti_swing_inbox.md`
- 语音想法 → 自动写 `thoughts/inbox.md`（已有，复用）
- 晚间语音复盘 → 自动填 `daily_log.md`
- 屏幕事件（项目目录 / Git / 报错）→ 卡点提醒

## V1.0 — 桌面仪表盘（计划）

接入 Hermes Desktop 首页：

```
今日组织度指数：__
主频目标：__
锁定剩余：__ 天
昨日产出：__
预警：__
今日主频咒语：__
```

详见 `prd.md` 的「未来形态：Hermes Reality Sampler」章节。

---

## 当前默认主频候选

根据 2026-06-21 项目盘面，候选主频包括：

1. `bucket-list-ai` — 真实 AI 联调
2. `hermes-desktop` — Record Flow 设计文档 / 现实采样器底座
3. `_ProjectOS` — FrequencyOS 自身 72h MVP

**首个主频目标需在 V0.1 启动 7 天内通过 `goals.md` 锁定协议正式签署。**

---

## 不做什么（边界守则）

- 不做打卡 App — 市场已饱和，没有方法论锋芒
- 不做心理治疗 — 定位为「目标一致性工具」
- 不做全自动行为监控 — V0.1 不接屏幕 / 可穿戴 / 生理数据
- 不做用户迎合 — 永远先问"这是不是高频噪音"
- 不做无限持仓 — 任何想法 / 目标 / 项目都必须进入 A→D 闭环

---

## 文档导航

| 文件 | 内容 |
|---|---|
| `control_layer.md` | 五层架构 + 三份文档来源映射（**先读这个**） |
| `prd.md` | 产品定义 + V0.2/V0.3/V1.0 路线 + 商业化 + Hermes Reality Sampler |
| `goals.md` | 目标锁定协议 + 当前主频 |
| `daily_log.md` | 每日采样表（最新在上） |
| `anti_swing_inbox.md` | 摇摆冲动缓冲池 |
| `weekly_report.md` | 周度频谱报告 |
| `templates/` | 四个空白模板 |
| `scripts/frequency_daily.py` | 独立采样合并入口 |
