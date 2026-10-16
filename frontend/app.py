import os

import streamlit as st

import api
import ui

st.set_page_config(page_title="Product Analytics + AI", page_icon=":material/insights:", layout="wide")
st.markdown(ui.CSS, unsafe_allow_html=True)

user = st.session_state.get("user")

if not user:
    pg = st.navigation([st.Page("views/login.py", title="Đăng nhập", icon=":material/login:")], position="hidden")
else:
    role = user["role"]
    analysis = [st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
                st.Page("views/ai_analysis.py", title="Phân tích AI", icon=":material/auto_awesome:")]
    data_pages = [st.Page("views/data_manager.py", title="Dữ liệu", icon=":material/database:")] if role in ("admin", "analyst") else []
    admin_pages = [st.Page("views/users.py", title="Người dùng", icon=":material/group:")] if role == "admin" else []
    sections = {"Phân tích": analysis}
    if data_pages:
        sections["Dữ liệu"] = data_pages
    if admin_pages:
        sections["Quản trị"] = admin_pages
    pg = st.navigation(sections)

    with st.sidebar:
        st.divider()
        st.markdown(f"**{user['full_name']}**")
        st.caption(user["email"])
        st.markdown(ui.role_badge(role), unsafe_allow_html=True)
        if st.button("Đăng xuất", icon=":material/logout:", use_container_width=True):
            api.logout()
            st.rerun()

pg.run()
