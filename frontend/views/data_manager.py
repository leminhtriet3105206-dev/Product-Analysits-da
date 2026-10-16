import pandas as pd
import plotly.express as px
import streamlit as st

import api
import ui

user = ui.require_role("admin", "analyst")
is_admin = user["role"] == "admin"

st.title("Dữ liệu")

PRESETS = {"Nhỏ": (50, 200, 600), "Vừa": (300, 1000, 4000), "Lớn": (2000, 8000, 40000)}
for k, v in {"gen_users": 300, "gen_sessions": 1000, "gen_events": 4000, "gen_days": 14}.items():
    st.session_state.setdefault(k, v)


def apply_preset(u, s, e):
    st.session_state.update(gen_users=u, gen_sessions=s, gen_events=e)


def overview_tab():
    ov = api.safe("GET", "/data/overview")
    if not ov:
        return
    c = st.columns(3)
    c[0].metric("Người dùng", ui.fmt(ov["visitors"]))
    c[1].metric("Phiên (session)", ui.fmt(ov["sessions"]))
    c[2].metric("Sự kiện (event)", ui.fmt(ov["events"]))
    if ov["first_session"]:
        st.caption(f"Dữ liệu từ {ov['first_session'][:10]} đến {ov['last_session'][:10]}")
    if ov["event_types"]:
        df = pd.DataFrame(ov["event_types"])
        df["event_type"] = df["event_type"].map(ui.STEP_LABEL)
        fig = px.bar(df, x="event_type", y="events", text="events", color_discrete_sequence=[ui.COLORS[0]],
                     title="Số sự kiện theo loại")
        fig.update_layout(height=320, margin=dict(t=50, b=10), xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True, key="ov_types")
    else:
        st.info("Chưa có dữ liệu." + (" Sang tab **Tạo dữ liệu** để thêm." if is_admin else ""))


def generate_tab():
    st.markdown("Chọn số lượng muốn tạo. Dữ liệu được sinh theo hành vi thực tế: truy cập → xem sản phẩm → thêm giỏ → thanh toán, "
                "người dùng di động bỏ giỏ hàng nhiều hơn.")
    if msg := st.session_state.pop("gen_msg", None):
        st.success(msg)
    cols = st.columns(len(PRESETS))
    for col, (name, (u, s, e)) in zip(cols, PRESETS.items()):
        col.button(f"{name}: {ui.fmt(u)} / {ui.fmt(s)} / {ui.fmt(e)}", on_click=apply_preset, args=(u, s, e), use_container_width=True)

    c1, c2, c3, c4 = st.columns(4)
    n_users = c1.number_input("Số người dùng (user)", 1, 20000, step=10, key="gen_users")
    n_sessions = c2.number_input("Số phiên (session)", 1, 50000, step=50, key="gen_sessions")
    n_events = c3.number_input("Số sự kiện (event)", 1, 200000, step=100, key="gen_events")
    days = c4.number_input("Rải trong N ngày gần nhất", 1, 365, key="gen_days")
    replace = st.radio("Cách ghi dữ liệu", ["Thêm vào dữ liệu hiện có", "Xóa dữ liệu cũ rồi tạo mới"], horizontal=True) == "Xóa dữ liệu cũ rồi tạo mới"

    problems = []
    if n_users > n_sessions:
        problems.append("Số user không được lớn hơn số session (mỗi user cần ít nhất 1 session).")
    if n_sessions > n_events:
        problems.append("Số session không được lớn hơn số event (mỗi session cần ít nhất 1 event).")
    if n_events > n_sessions * 20:
        problems.append("Số event tối đa là 20 lần số session.")
    for p in problems:
        st.error(p)
    if not problems:
        st.caption(f"Trung bình {n_sessions / n_users:.1f} phiên mỗi user, {n_events / n_sessions:.1f} sự kiện mỗi phiên.")

    if replace:
        st.warning("Toàn bộ session và event hiện có sẽ bị xóa trước khi tạo mới (tài khoản và lịch sử phân tích được giữ lại).")
    if st.button("Tạo dữ liệu", type="primary", icon=":material/add_circle:", disabled=bool(problems)):
        with st.spinner("Đang ghi vào PostgreSQL..."):
            res = api.safe("POST", "/data/generate", timeout=180, json={
                "n_users": int(n_users), "n_sessions": int(n_sessions), "n_events": int(n_events),
                "days": int(days), "replace": replace})
        if res:
            g = res["generated"]
            st.session_state["gen_msg"] = (
                f"Đã tạo {ui.fmt(g['users'])} user, {ui.fmt(g['sessions'])} session, {ui.fmt(g['events'])} event. "
                f"Tổng hiện có: {ui.fmt(res['overview']['sessions'])} session, {ui.fmt(res['overview']['events'])} event.")
            st.rerun()  # làm mới tab Tổng quan với số liệu mới

    with st.expander("Vùng nguy hiểm: xóa toàn bộ dữ liệu"):
        sure = st.checkbox("Tôi hiểu thao tác này xóa hết session và event")
        if st.button("Xóa dữ liệu", disabled=not sure, icon=":material/delete:"):
            if api.safe("DELETE", "/data"):
                st.session_state["gen_msg"] = "Đã xóa toàn bộ session và event."
                st.rerun()


def events_tab():
    c1, c2, c3 = st.columns(3)
    et = c1.selectbox("Loại sự kiện", ["Tất cả"] + [k for k in ui.STEP_LABEL])
    dv = c2.selectbox("Thiết bị", ["Tất cả"] + ui.DEVICES, format_func=lambda x: ui.DEVICE_LABEL.get(x, x))
    limit = c3.selectbox("Số dòng", [50, 100, 200, 500], index=1)
    params = {"limit": limit}
    if et != "Tất cả":
        params["event_type"] = et
    if dv != "Tất cả":
        params["device"] = dv
    rows = api.safe("GET", "/data/events", params=params)
    if rows is not None:
        if rows:
            df = pd.DataFrame(rows)
            df["properties"] = df["properties"].astype(str)
            st.dataframe(df, hide_index=True, use_container_width=True, height=420)
        else:
            st.info("Không có sự kiện phù hợp.")
    with st.expander("Gửi một sự kiện thử"):
        c1, c2 = st.columns(2)
        et2 = c1.selectbox("Loại", [k for k in ui.STEP_LABEL], key="ev_type")
        dv2 = c2.selectbox("Thiết bị ", ui.DEVICES, format_func=ui.DEVICE_LABEL.get, key="ev_dev")
        if st.button("Gửi sự kiện", key="send_ev"):
            if api.safe("POST", "/events", json={"visitor_id": "demo-visitor", "event_type": et2, "device": dv2, "page": "/demo"}):
                st.success("Đã ghi sự kiện. Làm mới bảng để thấy dòng mới.")


tabs = ["Tổng quan"] + (["Tạo dữ liệu"] if is_admin else []) + ["Xem sự kiện"]
for tab, name in zip(st.tabs(tabs), tabs):
    with tab:
        {"Tổng quan": overview_tab, "Tạo dữ liệu": generate_tab, "Xem sự kiện": events_tab}[name]()
