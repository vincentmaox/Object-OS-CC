"""三频共振评分 + 规则化 MVA 建议

用于让 daily_recap / 晨报卡片 / project_agent 共享同一套评分语义。
**也用于线下破壁场景的三频检查**（《茧房破壁操作系统 v1.0》第 11.2 章直接复用本规则）。

字段约定（registry.projects[name] 里）：
  freq_theory  : int 1-5  理论频谱（你能否用现有知识 72h 内交付 MVP）
  freq_market  : int 1-5  市场频谱（是否有付费意愿验证或差异化）
  freq_org     : int 1-5  组织频谱（是否在你能力圈内 + 维护成本可控）
  freq_total   : int 3-15 三项之和，写入时一并存（避免每次重算）
  freq_scored_at : ISO 时间戳

规则（来自《虚空建筑师野化宣言》第八部分）：
  - 任一维 = 0 → Kill（频率断裂，立刻砍）
  - 总分 ≥ 13 且最低维 ≥ 4 → All-in（三频共振强）
  - 总分 ≥ 10 → Watch（中频带，再观察 72h）
  - 其他 → Kill 候选

返回的建议是「规则化建议」，不是终审。daily_recap 把它丢给 LLM 当锚点用。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, TypedDict


class FreqScore(TypedDict, total=False):
    freq_theory: int
    freq_market: int
    freq_org: int
    freq_total: int
    freq_scored_at: str
    freq_suggestion: str


def compute_suggestion(theory: int, market: int, org: int) -> tuple[int, str, str]:
    """返回 (总分, 建议标签, 一句话理由)。

    建议标签 ∈ {"All-in", "Watch", "Kill"}。
    """
    total = theory + market + org
    lo = min(theory, market, org)

    if lo == 0:
        return total, "Kill", f"任一维=0（min={lo}），频率断裂"
    if total >= 13 and lo >= 4:
        return total, "All-in", f"总分 {total}/15 + 最低维 {lo}/5，三频共振"
    if total >= 10:
        return total, "Watch", f"总分 {total}/15，中频带需再观察 72h"
    return total, "Kill", f"总分 {total}/15 偏低，候选淘汰"


def build_freq_payload(theory: int, market: int, org: int) -> FreqScore:
    """生成完整的 freq 字段（写入 registry 用）。"""
    for v, name in ((theory, "theory"), (market, "market"), (org, "org")):
        if not (0 <= v <= 5):
            raise ValueError(f"freq_{name}={v} 超出 0-5")
    total, suggestion, _ = compute_suggestion(theory, market, org)
    return {
        "freq_theory": theory,
        "freq_market": market,
        "freq_org": org,
        "freq_total": total,
        "freq_suggestion": suggestion,
        "freq_scored_at": datetime.now().isoformat(timespec="seconds"),
    }


def render_freq_line(info: dict) -> Optional[str]:
    """从 registry 项目记录里抽出一行人类可读评分摘要，没评分返回 None。"""
    t = info.get("freq_theory")
    m = info.get("freq_market")
    o = info.get("freq_org")
    if t is None or m is None or o is None:
        return None
    total, suggestion, reason = compute_suggestion(int(t), int(m), int(o))
    return f"三频 理论{t}/市场{m}/组织{o} = {total}/15 → 规则建议: {suggestion}（{reason}）"
