import random
import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from .models import Event, VisitSession

MAX_EVENTS_PER_SESSION = 20
DEVICES = ["mobile", "desktop", "tablet"]
DEVICE_WEIGHTS = [55, 35, 10]
# Xác suất đi tiếp: (xem sản phẩm, thêm giỏ, thanh toán). Mobile bỏ giỏ hàng nhiều hơn.
FUNNEL_P = {"mobile": (0.62, 0.34, 0.20), "desktop": (0.70, 0.50, 0.42), "tablet": (0.66, 0.45, 0.35)}
STEPS = ["page_view", "view_product", "add_to_cart", "purchase"]
HOME_PAGES = ["/", "/blog", "/pricing", "/products"]
CHUNK = 5000


def validate(n_users: int, n_sessions: int, n_events: int) -> None:
    if n_users > n_sessions:
        raise HTTPException(422, "Số user không được lớn hơn số session (mỗi user cần ít nhất 1 session)")
    if n_sessions > n_events:
        raise HTTPException(422, "Số session không được lớn hơn số event (mỗi session cần ít nhất 1 event)")
    if n_events > n_sessions * MAX_EVENTS_PER_SESSION:
        raise HTTPException(422, f"Số event tối đa là {MAX_EVENTS_PER_SESSION} lần số session")


def _event_row(sid: str, device: str, etype: str, ts: datetime, rnd: random.Random) -> dict:
    if etype == "page_view":
        page, props = rnd.choice(HOME_PAGES), {"device": device}
    elif etype == "view_product":
        pid = rnd.randint(1, 30)
        page, props = f"/product/{pid}", {"device": device, "product_id": pid}
    elif etype == "add_to_cart":
        page, props = "/cart", {"device": device, "qty": rnd.randint(1, 3)}
    elif etype == "purchase":
        page, props = "/checkout", {"device": device, "amount": rnd.choice([99000, 199000, 349000, 499000])}
    else:
        page, props = rnd.choice(HOME_PAGES), {"device": device, "element": rnd.choice(["banner", "menu", "filter", "search"])}
    return {"session_id": sid, "event_type": etype, "page": page, "properties": props, "created_at": ts}


def generate(db: Session, n_users: int, n_sessions: int, n_events: int, days: int, replace: bool) -> dict:
    """Sinh dữ liệu giả với đúng số user / session / event được yêu cầu."""
    validate(n_users, n_sessions, n_events)
    rnd = random.Random()
    now = datetime.utcnow()
    if replace:
        db.execute(delete(Event))
        db.execute(delete(VisitSession))
        db.commit()

    # Rải đều từ 0h của ngày (hôm nay - (days-1)) đến gần hiện tại, để bộ lọc "N ngày" trên dashboard lấy đủ dữ liệu
    lo = datetime.combine(now.date(), datetime.min.time()) - timedelta(days=days - 1)
    hi = max(lo + timedelta(seconds=1), now - timedelta(seconds=2000))
    span = (hi - lo).total_seconds()
    tag = uuid.uuid4().hex[:4]
    visitors = [f"user-{tag}-{i:05d}" for i in range(n_users)]

    sessions, seqs = [], []
    for i in range(n_sessions):
        device = rnd.choices(DEVICES, weights=DEVICE_WEIGHTS)[0]
        p_view, p_cart, p_buy = FUNNEL_P[device]
        seq = ["page_view"]
        if rnd.random() < p_view:
            seq.append("view_product")
            if rnd.random() < p_cart:
                seq.append("add_to_cart")
                if rnd.random() < p_buy:
                    seq.append("purchase")
        visitor = visitors[i] if i < n_users else rnd.choice(visitors)  # mọi user có ít nhất 1 session
        start = lo + timedelta(seconds=rnd.uniform(0, span))
        sessions.append({"id": str(uuid.uuid4()), "visitor_id": visitor, "device": device, "started_at": start})
        seqs.append(seq)

    total = sum(len(s) for s in seqs)
    if total > n_events:  # bớt sự kiện sâu nhất của các phiên có >1 sự kiện
        cand = [i for i, s in enumerate(seqs) if len(s) > 1]
        while total > n_events:
            j = rnd.randrange(len(cand))
            i = cand[j]
            seqs[i].pop()
            total -= 1
            if len(seqs[i]) == 1:
                cand[j] = cand[-1]
                cand.pop()
    elif total < n_events:  # thêm sự kiện 'click' vào các phiên chưa đầy
        eligible = [i for i, s in enumerate(seqs) if len(s) < MAX_EVENTS_PER_SESSION]
        for _ in range(n_events - total):
            j = rnd.randrange(len(eligible))
            i = eligible[j]
            seqs[i].insert(rnd.randint(1, len(seqs[i])), "click")
            if len(seqs[i]) >= MAX_EVENTS_PER_SESSION:
                eligible[j] = eligible[-1]
                eligible.pop()

    for i in range(0, len(sessions), CHUNK):
        db.execute(insert(VisitSession), sessions[i:i + CHUNK])
    buf = []
    for s, seq in zip(sessions, seqs):
        t = s["started_at"]
        for etype in seq:
            t += timedelta(seconds=rnd.randint(4, 90))
            buf.append(_event_row(s["id"], s["device"], etype, t, rnd))
        if len(buf) >= CHUNK:
            db.execute(insert(Event), buf)
            buf = []
    if buf:
        db.execute(insert(Event), buf)
    db.commit()
    return {"users": n_users, "sessions": n_sessions, "events": n_events, "replace": replace}


def overview(db: Session) -> dict:
    first, last = db.execute(select(func.min(VisitSession.started_at), func.max(VisitSession.started_at))).one()
    return {
        "visitors": db.scalar(select(func.count(func.distinct(VisitSession.visitor_id)))) or 0,
        "sessions": db.scalar(select(func.count()).select_from(VisitSession)) or 0,
        "events": db.scalar(select(func.count()).select_from(Event)) or 0,
        "first_session": first.isoformat() if first else None,
        "last_session": last.isoformat() if last else None,
        "event_types": [{"event_type": k, "events": v} for k, v in db.execute(
            select(Event.event_type, func.count()).group_by(Event.event_type).order_by(func.count().desc())).all()],
    }
