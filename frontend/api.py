"""Gọi FastAPI backend, tự gắn token đăng nhập."""
import os

import requests
import streamlit as st

API = os.getenv("API_URL", "http://localhost:8000")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def logout() -> None:
    for k in list(st.session_state.keys()):
        del st.session_state[k]


def request(method: str, path: str, timeout: int = 60, **kw):
    headers = kw.pop("headers", {})
    token = st.session_state.get("token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.request(method, API + path, headers=headers, timeout=timeout, **kw)
    except requests.RequestException:
        raise ApiError(0, f"Không kết nối được tới API ({API}). Backend đã chạy chưa?")
    if r.ok:
        return r.json()
    try:
        detail = r.json().get("detail")
    except Exception:
        detail = r.text
    if isinstance(detail, list):  # lỗi validate của pydantic
        detail = "; ".join(str(d.get("msg", d)) for d in detail)
    raise ApiError(r.status_code, str(detail))


def safe(method: str, path: str, **kw):
    """Trả dữ liệu hoặc None (đã hiện lỗi). Hết phiên (401) thì đăng xuất về trang đăng nhập."""
    try:
        return request(method, path, **kw)
    except ApiError as e:
        if e.status == 401 and st.session_state.get("token"):
            logout()
            st.rerun()
        st.error(e.message)
        return None
