from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .deps import ADMIN, current_user, require_roles
from .models import User
from .schemas import LoginIn, RegisterIn, UserCreate, UserPatch
from .security import create_token, hash_password, verify_password

router = APIRouter()


def user_dict(u: User) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role, "is_active": u.is_active,
            "created_at": u.created_at, "last_login_at": u.last_login_at}


def _create(db: Session, email: str, password: str, full_name: str, role: str) -> User:
    email = email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email này đã được đăng ký")
    u = User(email=email, full_name=full_name.strip(), password_hash=hash_password(password), role=role)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@router.post("/auth/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """Tự đăng ký luôn có vai trò viewer; admin nâng quyền sau."""
    return user_dict(_create(db, body.email, body.password, body.full_name, "viewer"))


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Email hoặc mật khẩu không đúng")
    if not u.is_active:
        raise HTTPException(403, "Tài khoản đã bị khóa")
    u.last_login_at = datetime.utcnow()
    db.commit()
    return {"access_token": create_token(u.id, u.role), "token_type": "bearer", "user": user_dict(u)}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return user_dict(user)


@router.get("/users")
def list_users(db: Session = Depends(get_db), _: User = Depends(require_roles(ADMIN))):
    return [user_dict(u) for u in db.scalars(select(User).order_by(User.id)).all()]


@router.post("/users", status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(ADMIN))):
    return user_dict(_create(db, body.email, body.password, body.full_name, body.role))


@router.patch("/users/{user_id}")
def patch_user(user_id: int, body: UserPatch, db: Session = Depends(get_db), me: User = Depends(require_roles(ADMIN))):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "Không tìm thấy người dùng")
    if u.id == me.id and (body.role not in (None, ADMIN) or body.is_active is False):
        raise HTTPException(400, "Không thể tự hạ quyền hoặc khóa chính mình")
    if body.role is not None:
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active
    db.commit()
    return user_dict(u)
