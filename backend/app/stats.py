from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Event, VisitSession
from .schemas import DEVICES

FUNNEL = ["page_view", "view_product", "add_to_cart", "purchase"]


@dataclass
class Filters:
    since: datetime
    until: datetime | None
    devices: list[str] | None


def parse_devices(raw) -> list[str] | None:
    """Nhận 'mobile,desktop' hoặc list; trả None nếu không lọc."""
    if raw is None or raw == "" or raw == []:
        return None
    items = raw.split(",") if isinstance(raw, str) else list(raw)
    items = [i.strip() for i in items if i.strip()]
    bad = [i for i in items if i not in DEVICES]
    if bad:
        raise HTTPException(422, f"Thiết bị không hợp lệ: {', '.join(bad)}")
    return items or None


def make_filters(days: int, date_from: date | None, date_to: date | None, devices) -> Filters:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Ngày bắt đầu phải trước ngày kết thúc")
    if date_from or date_to:
        since = datetime.combine(date_from, time.min) if date_from else datetime(2000, 1, 1)
        until = datetime.combine(date_to, time.max) if date_to else None
    else:
        since, until = datetime.utcnow() - timedelta(days=days), None
    return Filters(since, until, parse_devices(devices))


def _conds(f: Filters) -> list:
    c = [VisitSession.started_at >= f.since]
    if f.until:
        c.append(VisitSession.started_at <= f.until)
    if f.devices:
        c.append(VisitSession.device.in_(f.devices))
    return c


def compute_stats(db: Session, f: Filters) -> dict:
    conds = _conds(f)
    join_on = Event.session_id == VisitSession.id

    sessions = db.scalar(select(func.count()).select_from(VisitSession).where(*conds)) or 0
    visitors = db.scalar(select(func.count(func.distinct(VisitSession.visitor_id))).where(*conds)) or 0
    events = db.scalar(select(func.count()).select_from(Event).join(VisitSession, join_on).where(*conds)) or 0

    per_type = dict(db.execute(
        select(Event.event_type, func.count()).select_from(Event).join(VisitSession, join_on)
        .where(*conds).group_by(Event.event_type)).all())
    sess_per_type = dict(db.execute(
        select(Event.event_type, func.count(func.distinct(Event.session_id))).select_from(Event)
        .join(VisitSession, join_on).where(*conds).group_by(Event.event_type)).all())
    funnel = [{"step": s, "sessions": sess_per_type.get(s, 0)} for s in FUNNEL]

    sub = (select(Event.session_id, func.count().label("n")).select_from(Event).join(VisitSession, join_on)
           .where(*conds).group_by(Event.session_id).subquery())
    bounced = db.scalar(select(func.count()).select_from(sub).where(sub.c.n == 1)) or 0

    day_col = func.date(VisitSession.started_at)
    by_day = {str(d): n for d, n in db.execute(
        select(day_col, func.count()).where(*conds).group_by(day_col)).all()}
    daily = []
    if by_day:
        start = max(f.since.date(), date.fromisoformat(min(by_day)))
        end = min((f.until or datetime.utcnow()).date(), date.fromisoformat(max(by_day)))
        d = start
        while d <= end:
            daily.append({"date": d.isoformat(), "sessions": by_day.get(d.isoformat(), 0)})
            d += timedelta(days=1)

    dev_rows = db.execute(select(VisitSession.device, func.count()).where(*conds).group_by(VisitSession.device)).all()
    buyers = dict(db.execute(
        select(VisitSession.device, func.count(func.distinct(Event.session_id))).select_from(Event)
        .join(VisitSession, join_on).where(Event.event_type == "purchase", *conds)
        .group_by(VisitSession.device)).all())
    devices = [{"device": d, "sessions": n,
                "conversion_pct": round(buyers.get(d, 0) / n * 100, 1) if n else 0.0} for d, n in dev_rows]

    return {
        "filters": {"since": f.since.date().isoformat(), "until": f.until.date().isoformat() if f.until else None,
                    "devices": f.devices or list(DEVICES)},
        "totals": {"visitors": visitors, "sessions": sessions, "events": events,
                   "bounce_rate": round(bounced / sessions * 100, 1) if sessions else 0.0,
                   "events_per_session": round(events / sessions, 2) if sessions else 0.0},
        "funnel": funnel,
        "event_counts": [{"event_type": k, "events": v} for k, v in sorted(per_type.items(), key=lambda x: -x[1])],
        "daily": daily,
        "devices": sorted(devices, key=lambda x: -x["sessions"]),
    }
