import os

import streamlit as st

import api

_, mid, _ = st.columns([1, 1.4, 1])
with mid:
    st.title("Product Analytics")
    st.caption("Phân tích hành vi người dùng, có AI tóm tắt")

    tab_login, tab_reg = st.tabs(["Đăng nhập", "Đăng ký"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Mật khẩu", type="password")
            ok = st.form_submit_button("Đăng nhập", type="primary", use_container_width=True)
        if ok:
            if not email or not password:
                st.warning("Nhập email và mật khẩu.")
            else:
                res = api.safe("POST", "/auth/login", json={"email": email, "password": password})
                if res:
                    st.session_state["token"] = res["access_token"]
                    st.session_state["user"] = res["user"]
                    st.rerun()
        if os.getenv("SHOW_DEMO_HINT", "true").lower() != "false":
            with st.expander("Tài khoản demo"):
                st.markdown(
                    "| Vai trò | Email | Mật khẩu |\n|---|---|---|\n"
                    "| Quản trị viên | admin@demo.com | admin123 |\n"
                    "| Nhà phân tích | analyst@demo.com | analyst123 |\n"
                    "| Người xem | viewer@demo.com | viewer123 |")

    with tab_reg:
        with st.form("register_form"):
            name = st.text_input("Họ và tên")
            email_r = st.text_input("Email", key="reg_email")
            pw1 = st.text_input("Mật khẩu (tối thiểu 6 ký tự)", type="password", key="reg_pw1")
            pw2 = st.text_input("Nhập lại mật khẩu", type="password", key="reg_pw2")
            ok_r = st.form_submit_button("Tạo tài khoản", use_container_width=True)
        if ok_r:
            if pw1 != pw2:
                st.error("Hai mật khẩu không khớp.")
            elif not name.strip():
                st.error("Nhập họ và tên.")
            else:
                res = api.safe("POST", "/auth/register", json={"email": email_r, "password": pw1, "full_name": name})
                if res:
                    st.success("Đăng ký thành công với vai trò Người xem. Hãy đăng nhập; quản trị viên có thể nâng quyền cho bạn.")
