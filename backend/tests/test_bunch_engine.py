from datetime import datetime, timedelta
from app.services.bunch_engine import classify_gap, detect_bunching

def test_classify_bunching():
    assert classify_gap(2.0, 8.0, 3.0, 15.0)[0] == "bunching"

def test_classify_large():
    assert classify_gap(16.0, 8.0, 3.0, 15.0)[0] == "large_gap"

def test_classify_normal():
    assert classify_gap(8.0, 8.0, 3.0, 15.0)[0] == "normal"

def test_detect_bunching_events():
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "A", "trip_no": "T1", "actual_arrive": base},
        {"stop_name": "A", "trip_no": "T2", "actual_arrive": base + timedelta(minutes=2)},
        {"stop_name": "A", "trip_no": "T3", "actual_arrive": base + timedelta(minutes=20)},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0)
    assert len(events) == 2
    assert events[0].status == "bunching"
    assert events[1].status == "large_gap"

def test_cross_line_pairs_marked_with_other_line():
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "S", "trip_no": "T1", "actual_arrive": base, "line_code": "B12"},
        {"stop_name": "S", "trip_no": "K1", "actual_arrive": base + timedelta(minutes=1), "line_code": "K7"},
        {"stop_name": "S", "trip_no": "T2", "actual_arrive": base + timedelta(minutes=8), "line_code": "B12"},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0, own_line_code="B12")
    cross = [e for e in events if e.cross_line]
    assert len(cross) == 2
    assert all(e.other_line == "K7" for e in cross)
    assert cross[0].earlier_trip == "T1" and cross[0].later_trip == "K1"
    assert cross[0].status == "bunching"
    assert cross[0].earlier_line == "B12" and cross[0].later_line == "K7"
    assert cross[1].earlier_trip == "K1" and cross[1].later_trip == "T2"
    assert cross[1].gap_min == 7.0

def test_own_pairs_kept_when_foreign_arrival_in_between():
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "S", "trip_no": "T1", "actual_arrive": base, "line_code": "B12"},
        {"stop_name": "S", "trip_no": "K1", "actual_arrive": base + timedelta(minutes=1), "line_code": "K7"},
        {"stop_name": "S", "trip_no": "T2", "actual_arrive": base + timedelta(minutes=2), "line_code": "B12"},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0, own_line_code="B12")
    own = [e for e in events if not e.cross_line]
    assert len(own) == 1
    assert own[0].earlier_trip == "T1" and own[0].later_trip == "T2"
    assert own[0].status == "bunching"

def test_foreign_pairs_not_in_own_report():
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "S", "trip_no": "T1", "actual_arrive": base, "line_code": "B12"},
        {"stop_name": "S", "trip_no": "K1", "actual_arrive": base + timedelta(minutes=4), "line_code": "K7"},
        {"stop_name": "S", "trip_no": "K2", "actual_arrive": base + timedelta(minutes=5), "line_code": "K7"},
        {"stop_name": "S", "trip_no": "T2", "actual_arrive": base + timedelta(minutes=9), "line_code": "B12"},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0, own_line_code="B12")
    assert not any(e.earlier_trip == "K1" and e.later_trip == "K2" for e in events)
    for e in events:
        if e.cross_line:
            assert {e.earlier_line, e.later_line} == {"B12", "K7"}

def test_no_line_code_behaves_as_single_line():
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "S", "trip_no": "T1", "actual_arrive": base},
        {"stop_name": "S", "trip_no": "T2", "actual_arrive": base + timedelta(minutes=2)},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0)
    assert len(events) == 1
    assert events[0].status == "bunching"
    assert not events[0].cross_line
    assert events[0].other_line == ""
