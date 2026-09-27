from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Line, SharedStop
router = APIRouter(prefix="/lines", tags=["lines"])

class SharedStopsIn(BaseModel):
    stop_names: list[str]

@router.get("")
def list_lines(db: Session = Depends(get_db)):
    rows = db.scalars(select(Line).order_by(Line.id)).all()
    return [{"id": r.id, "code": r.code, "name": r.name, "planned_headway_min": r.planned_headway_min,
             "bunch_threshold": r.bunch_threshold, "large_threshold": r.large_threshold,
             "shared_stops": [s.stop_name for s in r.shared_stops]} for r in rows]

@router.put("/{line_id}/shared_stops")
def put_shared_stops(line_id: int, body: SharedStopsIn, db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line: raise HTTPException(404, "线路不存在")
    names: list[str] = []
    for raw in body.stop_names:
        name = raw.strip()
        if name and name not in names: names.append(name)
    line.shared_stops = [SharedStop(stop_name=n) for n in names]
    db.commit()
    return {"line_id": line_id, "shared_stops": names}
