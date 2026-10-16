import pandas as pd
import streamlit as st

import api
import ui

user = st.session_state["user"]
can_run = user["role"] in ("admin", "analyst")

st.title("Phân tích AI")


def history_tab():
    rows = api.safe("GET", "/summaries", params={"limit": 20})
    if not rows:
        st.info("Chưa có bản phân tích nào.")
        return
    for r in rows:
        when = pd.to_datetime(r["created_at"]).strftime("%d/%m/%Y %H:%M")
        tag = {"rule": "Theo luật", "claude": "Claude", "gemini": "Gemini"}.get(r["source"], "AI")
        with st.expander(f"{when}  ·  {tag}  ·  {r['author'] or 'không rõ'}"):
            st.write(r["content"])
            p = r.get("params")
            if p:
                f = p["filters"]
                st.caption(f"Dữ liệu: {f['since']} → {f['until'] or 'nay'} · thiết bị: {', '.join(f['devices'])} · "
                           f"phần: {', '.join(ui.SECTIONS.get(s, s) for s in p['sections'])} · "
                           f"{ui.fmt(p['totals']['sessions'])} phiên, {ui.fmt(p['totals']['events'])} sự kiện")
            if r.get("question"):
                st.caption(f"Câu hỏi: {r['question']}")


if not can_run:
    st.caption("Tài khoản Người xem chỉ xem được các bản phân tích đã có.")
    history_tab()
    st.stop()

st.caption("Chọn dữ liệu muốn AI phân tích, kiểm tra lại số lượng, rồi bấm phân tích.")
tab_run, tab_hist = st.tabs(["Phân tích mới", "Lịch sử"])

with tab_run:
    with st.container(border=True):
        st.subheader("1. Chọn dữ liệu")
        flt = ui.filter_bar("ai")
        chosen = st.multiselect("Phần số liệu gửi cho AI", list(ui.SECTIONS), default=list(ui.SECTIONS),
                                format_func=ui.SECTIONS.get, key="ai_sections")

    stats = api.safe("GET", "/stats", params=ui.stats_params(flt))
    with st.container(border=True):
        st.subheader("2. Dữ liệu được chọn")
        if stats:
            t = stats["totals"]
            c = st.columns(4)
            c[0].metric("Người dùng", ui.fmt(t["visitors"]))
            c[1].metric("Phiên", ui.fmt(t["sessions"]))
            c[2].metric("Sự kiện", ui.fmt(t["events"]))
            c[3].metric("Tỷ lệ thoát", f"{t['bounce_rate']}%")

    with st.container(border=True):
        st.subheader("3. Câu hỏi thêm (tùy chọn)")
        question = st.text_area("Hỏi AI điều bạn quan tâm", placeholder="Ví dụ: Vì sao người dùng di động ít mua hàng hơn?",
                                max_chars=500, label_visibility="collapsed")

    empty = not stats or stats["totals"]["sessions"] == 0
    if empty:
        st.warning("Dữ liệu được chọn đang trống, hãy đổi bộ lọc.")
    if not chosen:
        st.warning("Chọn ít nhất một phần số liệu.")
    if st.button("Phân tích bằng AI", type="primary", icon=":material/auto_awesome:", disabled=empty or not chosen):
        with st.spinner("Đang phân tích..."):
            res = api.safe("POST", "/summary", timeout=90, json={
                "date_from": flt["date_from"], "date_to": flt["date_to"], "devices": flt["devices"],
                "sections": chosen, "question": question or None})
        if res:
            st.session_state["ai_result"] = res

    res = st.session_state.get("ai_result")
    if res:
        with st.container(border=True):
            st.subheader("Kết quả")
            st.success(res["content"])
             
            if res["source"] != "rule":
                st.caption(f"Nguồn: mô hình AI ({res['source'].capitalize()})")         
            else:
                st.caption("Nguồn: bản tóm tắt theo luật (chưa có API key hoặc AI không phản hồi)")
                if res.get("ai_error"):
                    st.warning(res["ai_error"])
            with st.expander("Số liệu đã gửi cho AI"):
                st.json(res["data_used"])

with tab_hist:
    history_tab()
