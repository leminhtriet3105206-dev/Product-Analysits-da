import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select, func

from . import api_analytics, api_auth, api_data
from .db import Base, SessionLocal, engine
from .migrate import ensure_columns
from .models import User
from .security import hash_password

DEMO_USERS = [
    ("admin@demo.com", "Quản trị viên", "admin123", "admin"),
    ("analyst@demo.com", "Nhà phân tích", "analyst123", "analyst"),
    ("viewer@demo.com", "Người xem", "viewer123", "viewer"),
]


def seed_users() -> None:
    """Lần chạy đầu: tạo tài khoản demo (tắt bằng SEED_DEMO_USERS=false, khi đó dùng ADMIN_EMAIL/ADMIN_PASSWORD)."""
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(User)):
            return
        if os.getenv("SEED_DEMO_USERS", "true").lower() != "false":
            users = DEMO_USERS
        elif os.getenv("ADMIN_EMAIL") and os.getenv("ADMIN_PASSWORD"):
            users = [(os.environ["ADMIN_EMAIL"], "Admin", os.environ["ADMIN_PASSWORD"], "admin")]
        else:
            return
        for email, name, pw, role in users:
            db.add(User(email=email, full_name=name, password_hash=hash_password(pw), role=role))
        db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    ensure_columns(engine)
    seed_users()
    yield


app = FastAPI(title="Product Analytics Demo", version="2.0", lifespan=lifespan)
app.include_router(api_auth.router)
app.include_router(api_data.router)
app.include_router(api_analytics.router)


@app.get("/health")
def health():
    return {"status": "ok"}
