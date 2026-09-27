import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Arrival, BunchReport, Line, SharedStop, Trip
from app.services.bunch_engine import detect_bunching, events_to_dicts
router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("")
def list_reports(db: Session = Depends(get_db)):
    rows = db.scalars(select(BunchReport).order_by(BunchReport.id.desc())).all()
    return [{"id": r.id, "line_id": r.line_id, "stop_name": r.stop_name,
             "created_at": r.created_at.isoformat(), "events": json.loads(r.summary_json)} for r in rows]

@router.post("/run")
def run_detection(line_id: int, stop_name: str | None = None, db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line: raise HTTPException(404, "线路不存在")
    trips = db.scalars(select(Trip).where(Trip.line_id == line_id)).all()
    trip_ids = [t.id for t in trips]
    trip_no_map = {t.id: t.trip_no for t in trips}
    arrivals = db.scalars(select(Arrival).where(Arrival.trip_id.in_(trip_ids))).all()
    payload = [{"stop_name": a.stop_name, "trip_no": trip_no_map[a.trip_id],
                "actual_arrive": a.actual_arrive, "line_code": line.code}
               for a in arrivals if stop_name is None or a.stop_name == stop_name]
    # 共用站：其它线路登记了同一站名时，把其在 该站的到站并入同一时间序；非共用站只检本线
    shared_names = [s.stop_name for s in line.shared_stops]
    if shared_names:
        partners: dict[str, set[int]] = {}
        rows = db.scalars(select(SharedStop).where(SharedStop.stop_name.in_(shared_names),
                                                   SharedStop.line_id != line_id)).all()
        for r in rows:
            partners.setdefault(r.stop_name, set()).add(r.line_id)
        for name, line_ids in partners.items():
            if stop_name is not None and name != stop_name: continue
            code_map = {l.id: l.code for l in db.scalars(select(Line).where(Line.id.in_(line_ids))).all()}
            other_trips = db.scalars(select(Trip).where(Trip.line_id.in_(line_ids))).all()
            other_trip_map = {t.id: t for t in other_trips}
            if not other_trip_map: continue
            other_arrivals = db.scalars(select(Arrival).where(Arrival.trip_id.in_(list(other_trip_map)),
                                                              Arrival.stop_name == name)).all()
            for a in other_arrivals:
                t = other_trip_map[a.trip_id]
                payload.append({"stop_name": a.stop_name, "trip_no": t.trip_no,
                                "actual_arrive": a.actual_arrive, "line_code": code_map[t.line_id]})
    events = detect_bunching(payload, line.planned_headway_min, line.bunch_threshold,
                             line.large_threshold, own_line_code=line.code)
    data = events_to_dicts(events)
    report = BunchReport(line_id=line_id, stop_name=stop_name or "*", created_at=datetime.utcnow(),
                         summary_json=json.dumps(data, ensure_ascii=False))
    db.add(report); db.commit(); db.refresh(report)
    return {"id": report.id, "events": data}

@router.get("/suggestions")
def suggestions(line_id: int, db: Session = Depends(get_db)):
    result = run_detection(line_id=line_id, stop_name=None, db=db)
    return {"line_id": line_id, "suggestions": [e for e in result["events"] if e["status"] != "normal"]}

@router.get("/timeline")
def timeline(line_id: int, stop_name: str = "市民中心", db: Session = Depends(get_db)):
    trips = db.scalars(select(Trip).where(Trip.line_id == line_id)).all()
    trip_ids = [t.id for t in trips]
    trip_no_map = {t.id: t.trip_no for t in trips}
    arrivals = sorted(db.scalars(select(Arrival).where(Arrival.trip_id.in_(trip_ids), Arrival.stop_name == stop_name)).all(),
                      key=lambda a: a.actual_arrive)
    if not arrivals: return {"stop_name": stop_name, "marks": []}
    t0 = arrivals[0].actual_arrive
    span = max((arrivals[-1].actual_arrive - t0).total_seconds(), 1)
    marks = [{"trip_no": trip_no_map[a.trip_id], "actual_arrive": a.actual_arrive.isoformat(),
              "pct": round((a.actual_arrive - t0).total_seconds() / span * 100, 2)} for a in arrivals]
    return {"stop_name": stop_name, "marks": marks}
