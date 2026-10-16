import random
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .models import Event, VisitSession


def seed_data(db: Session, sessions: int = 600, days: int = 14) -> int:
    """Sinh dữ liệu giả có quy luật: mobile bỏ giỏ hàng nhiều hơn desktop."""
    rnd = random.Random(42)
    now = datetime.utcnow()
    visitors = [f"user-{i}" for i in range(1, 251)]
    n_events = 0
    for _ in range(sessions):
        device = rnd.choices(["mobile", "desktop", "tablet"], weights=[55, 35, 10])[0]
        start = now - timedelta(days=rnd.random() * (days - 1), minutes=rnd.randint(0, 1000))
        sid = str(uuid.uuid4())
        db.add(VisitSession(id=sid, visitor_id=rnd.choice(visitors), device=device, started_at=start))
        p_view = 0.65
        p_cart = 0.38 if device == "mobile" else 0.5
        p_buy = 0.22 if device == "mobile" else 0.42
        steps = [("page_view", "/")]
        if rnd.random() < p_view:
            steps.append(("view_product", f"/product/{rnd.randint(1, 20)}"))
            if rnd.random() < p_cart:
                steps.append(("add_to_cart", "/cart"))
                if rnd.random() < p_buy:
                    steps.append(("purchase", "/checkout"))
        t = start
        for et, page in steps:
            t += timedelta(seconds=rnd.randint(5, 90))
            db.add(Event(session_id=sid, event_type=et, page=page, created_at=t, properties={"device": device}))
            n_events += 1
    db.commit()
    return n_events
