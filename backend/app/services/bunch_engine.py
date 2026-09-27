"""Bus bunching: planned headway vs actual arrival gaps.

共用站跨线判定：到站记录可带 line_code。detect_bunching 对每个站：
1. 本线相邻班次照常判定（本线内部的串车 / 大间隔保留，即使中间夹着他线到站）；
2. 把各线到站并入同一时间序，相邻且分属不同线路的一对记为跨线事件，
   并标明对方线路代号；与本线无关的他线对不进入本线报告。
不带 line_code 的记录视为本线，行为与旧版一致（非共用站只检本线）。
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
    earlier_line: str = ""
    later_line: str = ""
    other_line: str = ""

def classify_gap(gap_min: float, planned_headway_min: float, bunch_threshold: float, large_threshold: float) -> tuple[str, str]:
    if gap_min < bunch_threshold:
        return ("bunching", f"间隔 {gap_min:.1f} 分钟低于串车阈值 {bunch_threshold}，建议后车缓行或抽稀。")
    if gap_min > large_threshold:
        return ("large_gap", f"间隔 {gap_min:.1f} 分钟超过大间隔阈值 {large_threshold}，建议前车减速或加发。")
    return ("normal", f"间隔接近计划 {planned_headway_min:.1f} 分钟，保持即可。")

def _line_of(arrival: dict, own_line_code: str) -> str:
    return arrival.get("line_code") or own_line_code

def detect_bunching(arrivals: list[dict], planned_headway_min: float, bunch_threshold: float,
                    large_threshold: float, own_line_code: str = "") -> list[GapEvent]:
    by_stop: dict[str, list[dict]] = {}
    for a in arrivals:
        by_stop.setdefault(a["stop_name"], []).append(a)
    events: list[GapEvent] = []
    for stop, items in by_stop.items():
        own = sorted((a for a in items if _line_of(a, own_line_code) == own_line_code),
                     key=lambda x: x["actual_arrive"])
        merged = sorted(items, key=lambda x: x["actual_arrive"])
        staged: list[tuple[datetime, GapEvent]] = []
        # 本线相邻班次：与本线他线混排无关，始终保留
        for i in range(1, len(own)):
            prev, cur = own[i - 1], own[i]
            gap_min = (cur["actual_arrive"] - prev["actual_arrive"]).total_seconds() / 60.0
            status, suggestion = classify_gap(gap_min, planned_headway_min, bunch_threshold, large_threshold)
            staged.append((cur["actual_arrive"], GapEvent(
                stop, prev["trip_no"], cur["trip_no"], round(gap_min, 2), planned_headway_min,
                status, suggestion, earlier_line=own_line_code, later_line=own_line_code)))
        # 合并时间序上的跨线相邻对：标明对方线路代号
        for i in range(1, len(merged)):
            prev, cur = merged[i - 1], merged[i]
            prev_line, cur_line = _line_of(prev, own_line_code), _line_of(cur, own_line_code)
            if prev_line == cur_line:
                continue  # 同线相邻对已由本线判定覆盖
            if prev_line != own_line_code and cur_line != own_line_code:
                continue  # 与本线无关的他线对不进本线报告
            gap_min = (cur["actual_arrive"] - prev["actual_arrive"]).total_seconds() / 60.0
            status, suggestion = classify_gap(gap_min, planned_headway_min, bunch_threshold, large_threshold)
            other = cur_line if prev_line == own_line_code else prev_line
            suggestion = f"跨线配对（对方 {other}）：{suggestion}"
            staged.append((cur["actual_arrive"], GapEvent(
                stop, prev["trip_no"], cur["trip_no"], round(gap_min, 2), planned_headway_min,
                status, suggestion, cross_line=True,
                earlier_line=prev_line, later_line=cur_line, other_line=other)))
        staged.sort(key=lambda x: x[0])
        events.extend(ev for _, ev in staged)
    return events

def events_to_dicts(events: list[GapEvent]) -> list[dict]:
    return [asdict(e) for e in events]
