import json
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .deps import ADMIN, ALL_ROLES, ANALYST, require_roles
from .models import AISummary, Event, User, VisitSession
from .schemas import SECTIONS, EventIn, SummaryIn
from .stats import compute_stats, make_filters
from .summary import ai_summary, rule_based_summary, select_data

router = APIRouter()


@router.get("/stats")
def stats(days: int = Query(14, ge=1, le=365), date_from: date | None = None, date_to: date | None = None,
          devices: str | None = None, db: Session = Depends(get_db), _: User = Depends(require_roles(*ALL_ROLES))):
    return compute_stats(db, make_filters(days, date_from, date_to, devices))


@router.post("/events", status_code=201)
def add_event(e: EventIn, db: Session = Depends(get_db), _: User = Depends(require_roles(ADMIN, ANALYST))):
    sid = e.session_id or str(uuid.uuid4())
    ts = e.created_at or datetime.utcnow()
    if not db.get(VisitSession, sid):
        db.add(VisitSession(id=sid, visitor_id=e.visitor_id, device=e.device, started_at=ts))
        db.flush()
    db.add(Event(session_id=sid, event_type=e.event_type, page=e.page, properties=e.properties, created_at=ts))
    db.commit()
    return {"session_id": sid}


@router.post("/summary")
def make_summary(req: SummaryIn, db: Session = Depends(get_db), user: User = Depends(require_roles(ADMIN, ANALYST))):
    sections = [s for s in req.sections if s in SECTIONS]
    if not sections:
        raise HTTPException(422, "Hãy chọn ít nhất một phần số liệu để AI phân tích")
    flt = make_filters(req.days, req.date_from, req.date_to, req.devices)
    stats_all = compute_stats(db, flt)
    if stats_all["totals"]["sessions"] == 0:
        raise HTTPException(422, "Dữ liệu được chọn không có phiên nào để phân tích")
    data = select_data(stats_all, sections)
    question = (req.question or "").strip() or None

    text, ai_error, provider = ai_summary(data, question)
    source = provider or "rule"  # "claude" | "gemini" | "rule"
    if text is None:
        text, source = rule_based_summary(stats_all, sections, question), "rule"

    now = datetime.utcnow()
    params = {"filters": stats_all["filters"], "sections": sections, "totals": stats_all["totals"]}
    row = AISummary(period_start=flt.since, period_end=flt.until or now, source=source, content=text,
                    user_id=user.id, params=json.dumps(params, default=str), question=question)
    db.add(row)
    db.commit()
    return {"id": row.id, "source": source, "content": text, "created_at": row.created_at,
            "ai_error": ai_error, "data_used": data, "params": params, "question": question}


@router.get("/summaries")
def list_summaries(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
                   _: User = Depends(require_roles(*ALL_ROLES))):
    rows = db.execute(select(AISummary, User.email).outerjoin(User, AISummary.user_id == User.id)
                      .order_by(AISummary.id.desc()).limit(limit)).all()
    return [{"id": s.id, "source": s.source, "content": s.content, "created_at": s.created_at, "author": email,
             "question": s.question, "params": json.loads(s.params) if s.params else None} for s, email in rows]
