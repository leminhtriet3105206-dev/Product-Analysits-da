# Product Analytics có AI tóm tắt hành vi người dùng

Kiến trúc 3 lớp: **Streamlit** (giao diện) → **FastAPI** (xử lý, đăng nhập, phân quyền) → **PostgreSQL** (dữ liệu).

## Chạy bằng Docker

```bash
docker compose up --build
```

- Dashboard: http://localhost:8501
- Tài liệu API (Swagger): http://localhost:8000/docs

> **Đã chạy bản cũ trước đó?** Chạy lại bình thường, hệ thống tự thêm bảng `users` và các cột mới, dữ liệu cũ vẫn giữ.
> Muốn làm sạch hoàn toàn: `docker compose down -v` rồi `docker compose up --build`.

### Tài khoản demo (tạo tự động ở lần chạy đầu)

| Vai trò | Email | Mật khẩu |
|---|---|---|
| Quản trị viên | admin@demo.com | admin123 |
| Nhà phân tích | analyst@demo.com | analyst123 |
| Người xem | viewer@demo.com | viewer123 |

Người tự đăng ký luôn là **Người xem**; quản trị viên nâng quyền trong trang **Người dùng**.

### Phân quyền

| Chức năng | Người xem | Nhà phân tích | Quản trị viên |
|---|:-:|:-:|:-:|
| Xem dashboard, lọc dữ liệu | ✔ | ✔ | ✔ |
| Xem lịch sử phân tích AI | ✔ | ✔ | ✔ |
| Chọn dữ liệu và chạy phân tích AI | | ✔ | ✔ |
| Xem bảng sự kiện, gửi sự kiện thử | | ✔ | ✔ |
| Tạo / xóa dữ liệu (user, session, event) | | | ✔ |
| Quản lý tài khoản (vai trò, khóa, tạo mới) | | | ✔ |

Quyền được kiểm tra ở **API** (HTTP 401/403), giao diện chỉ ẩn trang tương ứng.

## Các chức năng chính

**Tạo dữ liệu theo số lượng (admin, trang Dữ liệu → Tạo dữ liệu):** nhập đúng số user, số session, số event.
Điều kiện: `user ≤ session ≤ event ≤ 20 × session`. Có thể thêm vào dữ liệu cũ hoặc xóa rồi tạo mới.
Dữ liệu sinh theo phễu truy cập → xem sản phẩm → thêm giỏ → thanh toán; mobile bỏ giỏ hàng nhiều hơn desktop.

**Chọn dữ liệu cho AI (trang Phân tích AI):** chọn khoảng thời gian, thiết bị và phần số liệu (tổng quan, phễu, theo ngày, theo thiết bị),
xem ngay số user / session / event được chọn, thêm câu hỏi tự do, rồi bấm phân tích. AI chỉ nhận đúng phần dữ liệu đã chọn.

**AI thật:** sao chép `.env.example` thành `.env`, điền `ANTHROPIC_API_KEY`, chạy lại `docker compose up`.
Không có key thì dùng bản tóm tắt theo luật (vẫn chạy, nhưng không trả lời được câu hỏi tự do).

## Kịch bản demo (khoảng 4 phút)

1. Đăng nhập `admin@demo.com`. Vào **Dữ liệu → Tạo dữ liệu**, nhập 300 user / 1.000 session / 4.000 event, bấm **Tạo dữ liệu**.
2. Mở psql để chỉ dữ liệu thật trong PostgreSQL: `docker compose exec db psql -U analytics -d analytics`, gõ `\dt` và `SELECT COUNT(*) FROM events;`.
3. **Dashboard:** chỉ vào thẻ số liệu, biểu đồ phiên theo ngày, phễu, thiết bị (mobile mua ít hơn).
4. **Phân tích AI:** chọn riêng thiết bị "Di động", bỏ vài phần số liệu, hỏi "Vì sao người dùng di động ít mua hàng?", bấm phân tích.
5. Đăng xuất, đăng nhập `viewer@demo.com`: chỉ thấy Dashboard và lịch sử, không có nút phân tích. Đây là phần phân quyền.

## Chạy không cần Docker (SQLite)

```bash
cd backend
pip install -r requirements.txt     # lỗi psycopg2? cài: pip install fastapi "uvicorn[standard]" sqlalchemy httpx pydantic pyjwt
uvicorn app.main:app --reload

cd frontend
pip install -r requirements.txt
streamlit run app.py
```

Dùng PostgreSQL có sẵn: đặt `DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/db`.

## Kiểm thử

```bash
cd backend
pip install pytest
pytest tests -q
```

21 test gồm đăng nhập, ma trận phân quyền, tạo dữ liệu đúng số lượng, bộ lọc, tóm tắt theo dữ liệu đã chọn, quản lý tài khoản.

## Cấu trúc

| File | Vai trò |
|---|---|
| `backend/app/models.py` | Bảng: users, sessions, events (JSONB), ai_summaries |
| `backend/app/security.py`, `deps.py` | Băm mật khẩu (PBKDF2), JWT, kiểm tra vai trò |
| `backend/app/api_auth.py` | Đăng ký, đăng nhập, quản lý người dùng |
| `backend/app/api_data.py`, `datagen.py` | Tổng quan dữ liệu, sinh dữ liệu theo số lượng, xem sự kiện |
| `backend/app/api_analytics.py`, `stats.py`, `summary.py` | Thống kê có bộ lọc, phân tích AI |
| `frontend/app.py`, `views/*.py` | Giao diện nhiều trang theo vai trò |

## Trước khi đưa lên mạng thật

Đổi `JWT_SECRET`, đặt `SEED_DEMO_USERS=false` và `SHOW_DEMO_HINT=false` (rồi tạo admin qua `ADMIN_EMAIL`/`ADMIN_PASSWORD`), và chạy sau HTTPS.
