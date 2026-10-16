import pandas as pd
import plotly.express as px
import streamlit as st

import api
import ui

st.title("Dashboard")
st.caption("Số liệu hành vi người dùng theo bộ lọc bên dưới")

with st.container(border=True):
    flt = ui.filter_bar("dash")

data = api.safe("GET", "/stats", params=ui.stats_params(flt))
if not data:
    st.stop()

t = data["totals"]
if t["sessions"] == 0:
    role = st.session_state["user"]["role"]
    hint = " Vào trang **Dữ liệu** để tạo dữ liệu mẫu." if role == "admin" else " Hãy nhờ quản trị viên nạp dữ liệu, hoặc mở rộng bộ lọc."
    st.info("Không có dữ liệu trong bộ lọc này." + hint)
    st.stop()

fn = {f["step"]: f["sessions"] for f in data["funnel"]}
conv = fn["purchase"] / fn["page_view"] * 100 if fn["page_view"] else 0

c = st.columns(5)
c[0].metric("Người dùng", ui.fmt(t["visitors"]))
c[1].metric("Phiên (session)", ui.fmt(t["sessions"]))
c[2].metric("Sự kiện (event)", ui.fmt(t["events"]), help=f"Trung bình {t['events_per_session']} sự kiện mỗi phiên")
c[3].metric("Tỷ lệ thoát", f"{t['bounce_rate']}%", help="Phiên chỉ có đúng 1 sự kiện")
c[4].metric("Chuyển đổi", f"{conv:.1f}%", help="Phiên có thanh toán / phiên có truy cập")

left, right = st.columns(2)
with left:
    with st.container(border=True):
        df = pd.DataFrame(data["daily"])
        fig = px.area(df, x="date", y="sessions", title="Số phiên theo ngày", color_discrete_sequence=[ui.COLORS[0]])
        fig.update_layout(margin=dict(t=50, b=10, l=10, r=10), height=340, xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True, key="daily")
with right:
    with st.container(border=True):
        f = pd.DataFrame(data["funnel"])
        f["step"] = f["step"].map(ui.STEP_LABEL)
        fig = px.funnel(f, x="sessions", y="step", title="Phễu chuyển đổi", color_discrete_sequence=[ui.COLORS[1]])
        fig.update_layout(margin=dict(t=50, b=10, l=10, r=10), height=340, yaxis_title=None, xaxis_title=None)
        st.plotly_chart(fig, use_container_width=True, key="funnel")

left, right = st.columns(2)
dev = pd.DataFrame(data["devices"])
dev["label"] = dev["device"].map(ui.DEVICE_LABEL)
with left:
    with st.container(border=True):
        fig = px.pie(dev, names="label", values="sessions", hole=0.55, title="Phiên theo thiết bị",
                     color_discrete_sequence=ui.COLORS)
        fig.update_layout(margin=dict(t=50, b=10, l=10, r=10), height=320)
        st.plotly_chart(fig, use_container_width=True, key="dev_pie")
with right:
    with st.container(border=True):
        fig = px.bar(dev, x="label", y="conversion_pct", text="conversion_pct", title="Tỷ lệ mua hàng theo thiết bị (%)",
                     color_discrete_sequence=[ui.COLORS[2]])
        fig.update_layout(margin=dict(t=50, b=10, l=10, r=10), height=320, xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True, key="dev_bar")

with st.expander("Số lượng sự kiện theo loại"):
    ev = pd.DataFrame(data["event_counts"])
    ev["event_type"] = ev["event_type"].map(ui.STEP_LABEL)
    st.dataframe(ev.rename(columns={"event_type": "Loại sự kiện", "events": "Số lượng"}), hide_index=True, use_container_width=True)
