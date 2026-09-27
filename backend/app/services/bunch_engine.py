"""Bus bunching: planned headway vs actual arrival gaps.

共用站（shared stops）可由多条线路登记：在共用站上，本线与其它共用线的
到站会并入同一时间序做相邻间隔判定，跨线相邻对会标注对方线路代号。
非共用站只对本线班次做判定。
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime

@dataclass
class GapEvent:
    stop_name: str
    earlier_trip: str
    later_trip: str
    gap_min: float
    planned_headway_min: float
    status: str
    suggestion: str
    cross_line: bool = False
    other_line_code: str | None = None

def classify_gap(gap_min: float, planned_headway_min: float, bunch_threshold: float, large_threshold: float) -> tuple[str, str]:
    if gap_min < bunch_threshold:
        return ("bunching", f"间隔 {gap_min:.1f} 分钟低于串车阈值 {bunch_threshold}，建议后车缓行或抽稀。")
    if gap_min > large_threshold:
        return ("large_gap", f"间隔 {gap_min:.1f} 分钟超过大间隔阈值 {large_threshold}，建议前车减速或加发。")
    return ("normal", f"间隔接近计划 {planned_headway_min:.1f} 分钟，保持即可。")

def _counterpart_code(prev: dict, cur: dict, report_line_id) -> str | None:
    """返回这对班次中"对方线路"的代号（相对出报告的本线）。"""
    prev_other = prev["line_id"] != report_line_id
    cur_other = cur["line_id"] != report_line_id
    if not prev_other and not cur_other:
        return None
    if cur_other and not prev_other:
        return cur["line_code"]
    if prev_other and not cur_other:
        return prev["line_code"]
    # 两条都不是本线（三条及以上线路共用时可能出现）
    return f'{prev["line_code"]}/{cur["line_code"]}'

def detect_bunching(
    arrivals: list[dict],
    planned_headway_min: float,
    bunch_threshold: float,
    large_threshold: float,
    shared_stop_names: set[str] | None = None,
    report_line_id=None,
) -> list[GapEvent]:
    shared_stop_names = shared_stop_names or set()
    # 未标注线路的到站视为本线班次（保持旧调用兼容）
    for a in arrivals:
        a.setdefault("line_id", report_line_id)
        a.setdefault("line_code", None)

    by_stop: dict[str, list[dict]] = {}
    for a in arrivals:
        by_stop.setdefault(a["stop_name"], []).append(a)

    events: list[GapEvent] = []
    for stop, items in by_stop.items():
        is_shared = stop in shared_stop_names
        if is_shared:
            # 共用站：所有共用线的到站并入同一时间序
            candidates = items
        elif report_line_id is not None:
            # 非共用站：只检本线
            candidates = [a for a in items if a["line_id"] == report_line_id]
        else:
            candidates = items
        candidates = sorted(candidates, key=lambda x: (x["actual_arrive"], x["line_id"] or 0, x["trip_no"]))
        for i in range(1, len(candidates)):
            prev, cur = candidates[i - 1], candidates[i]
            gap_min = (cur["actual_arrive"] - prev["actual_arrive"]).total_seconds() / 60.0
            status, suggestion = classify_gap(gap_min, planned_headway_min, bunch_threshold, large_threshold)
            cross = prev["line_id"] != cur["line_id"]
            other_code = _counterpart_code(prev, cur, report_line_id) if cross else None
            if cross:
                suggestion = f"【跨线·对方 {other_code}】{suggestion}"
            events.append(GapEvent(
                stop, prev["trip_no"], cur["trip_no"], round(gap_min, 2),
                planned_headway_min, status, suggestion,
                cross_line=cross, other_line_code=other_code,
            ))
    return events

def events_to_dicts(events: list[GapEvent]) -> list[dict]:
    return [asdict(e) for e in events]
