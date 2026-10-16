import pandas as pd
import streamlit as st

import api
import ui

me = ui.require_role("admin")

st.title("Quản lý người dùng")
st.caption("Phân quyền: Quản trị viên (toàn quyền) · Nhà phân tích (xem, chạy AI, xem sự kiện) · Người xem (chỉ xem)")

users = api.safe("GET", "/users")
if users:
    df = pd.DataFrame(users)
    df["Vai trò"] = df["role"].map(ui.ROLE_LABEL)
    df["Trạng thái"] = df["is_active"].map({True: "Đang hoạt động", False: "Đã khóa"})
    df["Đăng nhập gần nhất"] = pd.to_datetime(df["last_login_at"]).dt.strftime("%d/%m/%Y %H:%M").fillna("Chưa đăng nhập")
    st.dataframe(df[["id", "full_name", "email", "Vai trò", "Trạng thái", "Đăng nhập gần nhất"]].rename(
        columns={"id": "ID", "full_name": "Họ tên", "email": "Email"}), hide_index=True, use_container_width=True)

    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("Đổi vai trò / khóa tài khoản")
        with st.form("edit_user"):
            opts = {f"{u['full_name']} ({u['email']})": u for u in users}
            label = st.selectbox("Người dùng", list(opts))
            sel = opts[label]
            role = st.selectbox("Vai trò", list(ui.ROLE_LABEL), index=list(ui.ROLE_LABEL).index(sel["role"]), format_func=ui.ROLE_LABEL.get)
            active = st.toggle("Cho phép đăng nhập", value=sel["is_active"])
            if st.form_submit_button("Lưu thay đổi", type="primary"):
                if api.safe("PATCH", f"/users/{sel['id']}", json={"role": role, "is_active": active}):
                    st.success("Đã cập nhật.")
                    st.rerun()
    with right, st.container(border=True):
        st.subheader("Tạo tài khoản mới")
        with st.form("create_user", clear_on_submit=True):
            name = st.text_input("Họ và tên")
            email = st.text_input("Email")
            pw = st.text_input("Mật khẩu (tối thiểu 6 ký tự)", type="password")
            role_n = st.selectbox("Vai trò", list(ui.ROLE_LABEL), index=2, format_func=ui.ROLE_LABEL.get, key="new_role")
            if st.form_submit_button("Tạo tài khoản"):
                if api.safe("POST", "/users", json={"email": email, "password": pw, "full_name": name, "role": role_n}):
                    st.success("Đã tạo tài khoản.")
                    st.rerun()
