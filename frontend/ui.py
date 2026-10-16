"""Hằng số và thành phần giao diện dùng chung."""
import datetime as dt

import streamlit as st

DEVICES = ["mobile", "desktop", "tablet"]
DEVICE_LABEL = {"mobile": "Di động", "desktop": "Máy tính", "tablet": "Máy tính bảng"}
STEP_LABEL = {"page_view": "Truy cập", "view_product": "Xem sản phẩm", "add_to_cart": "Thêm giỏ hàng", "purchase": "Thanh toán", "click": "Click"}
ROLE_LABEL = {"admin": "Quản trị viên", "analyst": "Nhà phân tích", "viewer": "Người xem"}
SECTIONS = {"overview": "Tổng quan", "funnel": "Phễu chuyển đổi", "daily": "Xu hướng theo ngày", "devices": "Theo thiết bị"}
COLORS = ["#0E7C86", "#336791", "#F2A541", "#D93636", "#5F6F82"]

CSS = """
<style>
[data-testid="stMetric"] {background:#fff;border:1px solid #D5DEE8;border-radius:12px;padding:14px 18px;}
[data-testid="stMetricLabel"] p {color:#5F6F82;font-size:0.85rem;}
.role-badge {display:inline-block;padding:2px 10px;border-radius:999px;font-size:0.78rem;font-weight:600;color:#fff;}
.role-admin {background:#D93636;} .role-analyst {background:#0E7C86;} .role-viewer {background:#5F6F82;}
.block-container {padding-top:2.2rem;}
</style>
"""


def fmt(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def require_role(*roles: str) -> dict:
    user = st.session_state.get("user")
    if not user or user["role"] not in roles:
        st.error("Bạn không có quyền truy cập trang này.")
        st.stop()
    return user


def filter_bar(prefix: str) -> dict:
    """Bộ lọc khoảng thời gian + thiết bị. Trả về dict dùng cho cả GET /stats và POST /summary."""
    today = dt.date.today()
    c1, c2 = st.columns([3, 2])
    with c1:
        preset = st.radio("Khoảng thời gian", ["7 ngày", "14 ngày", "30 ngày", "Tùy chọn"], index=1,
                          horizontal=True, key=f"{prefix}_preset")
        if preset == "Tùy chọn":
            rng = st.date_input("Từ ngày – đến ngày", value=(today - dt.timedelta(days=13), today), key=f"{prefix}_range")
            if isinstance(rng, (tuple, list)) and len(rng) == 2:
                d_from, d_to = rng
            else:
                st.info("Hãy chọn đủ ngày bắt đầu và ngày kết thúc.")
                d_from, d_to = today - dt.timedelta(days=13), today
        else:
            n = int(preset.split()[0])
            d_from, d_to = today - dt.timedelta(days=n - 1), today
    with c2:
        devices = st.multiselect("Thiết bị", DEVICES, default=DEVICES, format_func=DEVICE_LABEL.get, key=f"{prefix}_devices")
        if not devices:
            st.caption("Chưa chọn thiết bị nào, hệ thống sẽ lấy tất cả.")
            devices = list(DEVICES)
    return {"date_from": d_from.isoformat(), "date_to": d_to.isoformat(), "devices": devices}


def stats_params(f: dict) -> dict:
    return {"date_from": f["date_from"], "date_to": f["date_to"], "devices": ",".join(f["devices"])}


def role_badge(role: str) -> str:
    return f'<span class="role-badge role-{role}">{ROLE_LABEL.get(role, role)}</span>'
