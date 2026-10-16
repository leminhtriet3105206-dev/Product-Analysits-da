from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .datagen import generate, overview
from .db import get_db
from .deps import ADMIN, ALL_ROLES, ANALYST, require_roles
from .models import Event, User, VisitSession
from .schemas import GenerateIn

router = APIRouter()


@router.get("/data/overview")
def data_overview(db: Session = Depends(get_db), _: User = Depends(require_roles(*ALL_ROLES))):
    return overview(db)


@router.post("/data/generate")
def data_generate(body: GenerateIn, db: Session = Depends(get_db), _: User = Depends(require_roles(ADMIN))):
    result = generate(db, body.n_users, body.n_sessions, body.n_events, body.days, body.replace)
    return {"generated": result, "overview": overview(db)}


@router.delete("/data")
def data_clear(db: Session = Depends(get_db), _: User = Depends(require_roles(ADMIN))):
    """Xóa toàn bộ sessions + events (giữ lại tài khoản và lịch sử tóm tắt)."""
    db.execute(delete(Event))
    db.execute(delete(VisitSession))
    db.commit()
    return overview(db)


@router.get("/data/events")
def data_events(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                event_type: str | None = None, device: str | None = None,
                db: Session = Depends(get_db), _: User = Depends(require_roles(ADMIN, ANALYST))):
    q = select(Event, VisitSession.visitor_id, VisitSession.device).join(VisitSession, Event.session_id == VisitSession.id)
    if event_type:
        q = q.where(Event.event_type == event_type)
    if device:
        q = q.where(VisitSession.device == device)
    rows = db.execute(q.order_by(Event.id.desc()).limit(limit).offset(offset)).all()
    return [{"id": e.id, "created_at": e.created_at, "visitor_id": v, "session_id": e.session_id, "device": d,
             "event_type": e.event_type, "page": e.page, "properties": e.properties} for e, v, d in rows]
