import os
import tempfile

# Phải đặt trước khi import app
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["JWT_SECRET"] = "test-secret"
os.environ.pop("ANTHROPIC_API_KEY", None)

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def login(client, email, pw):
    r = client.post("/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def tokens(client):
    return {
        "admin": login(client, "admin@demo.com", "admin123"),
        "analyst": login(client, "analyst@demo.com", "analyst123"),
        "viewer": login(client, "viewer@demo.com", "viewer123"),
    }


def test_auth_required(client):
    assert client.get("/stats").status_code == 401
    assert client.get("/stats", headers={"Authorization": "Bearer abc"}).status_code == 401


def test_wrong_password(client):
    r = client.post("/auth/login", json={"email": "admin@demo.com", "password": "sai"})
    assert r.status_code == 401


def test_register_is_viewer_and_duplicate(client):
    r = client.post("/auth/register", json={"email": "sv@x.com", "password": "123456", "full_name": "SV"})
    assert r.status_code == 201 and r.json()["role"] == "viewer"
    assert client.post("/auth/register", json={"email": "SV@x.com", "password": "123456", "full_name": "SV"}).status_code == 409
    assert client.post("/auth/register", json={"email": "bad", "password": "123456", "full_name": "SV"}).status_code == 422


def test_role_matrix(client, tokens):
    body = {"n_users": 5, "n_sessions": 10, "n_events": 20, "days": 7, "replace": True}
    assert client.post("/data/generate", json=body, headers=tokens["analyst"]).status_code == 403
    assert client.post("/data/generate", json=body, headers=tokens["viewer"]).status_code == 403
    assert client.get("/users", headers=tokens["analyst"]).status_code == 403
    assert client.post("/summary", json={}, headers=tokens["viewer"]).status_code == 403
    assert client.get("/data/events", headers=tokens["viewer"]).status_code == 403
    assert client.get("/stats", headers=tokens["viewer"]).status_code == 200
    assert client.get("/data/events", headers=tokens["analyst"]).status_code == 200


@pytest.mark.parametrize("u,s,e", [(10, 40, 40), (10, 40, 55), (30, 100, 100), (50, 200, 1200), (100, 300, 700), (1, 1, 1), (7, 7, 140)])
def test_generate_exact_counts(client, tokens, u, s, e):
    r = client.post("/data/generate", json={"n_users": u, "n_sessions": s, "n_events": e, "days": 10, "replace": True}, headers=tokens["admin"])
    assert r.status_code == 200, r.text
    ov = r.json()["overview"]
    assert (ov["visitors"], ov["sessions"], ov["events"]) == (u, s, e)


@pytest.mark.parametrize("u,s,e", [(10, 5, 50), (5, 10, 9), (5, 10, 201)])
def test_generate_validation(client, tokens, u, s, e):
    r = client.post("/data/generate", json={"n_users": u, "n_sessions": s, "n_events": e}, headers=tokens["admin"])
    assert r.status_code == 422


def test_append_mode(client, tokens):
    client.post("/data/generate", json={"n_users": 5, "n_sessions": 20, "n_events": 40, "replace": True}, headers=tokens["admin"])
    r = client.post("/data/generate", json={"n_users": 5, "n_sessions": 20, "n_events": 40, "replace": False}, headers=tokens["admin"])
    ov = r.json()["overview"]
    assert ov["sessions"] == 40 and ov["events"] == 80


def test_stats_filters(client, tokens):
    client.post("/data/generate", json={"n_users": 50, "n_sessions": 300, "n_events": 700, "days": 14, "replace": True}, headers=tokens["admin"])
    h = tokens["viewer"]
    allr = client.get("/stats", params={"days": 30}, headers=h).json()
    assert allr["totals"]["sessions"] == 300 and allr["totals"]["events"] == 700
    mob = client.get("/stats", params={"days": 30, "devices": "mobile"}, headers=h).json()
    desk = client.get("/stats", params={"days": 30, "devices": "desktop,tablet"}, headers=h).json()
    assert mob["totals"]["sessions"] + desk["totals"]["sessions"] == 300
    assert mob["totals"]["events"] + desk["totals"]["events"] == 700
    assert {d["device"] for d in mob["devices"]} == {"mobile"}
    funnel = [f["sessions"] for f in allr["funnel"]]
    assert funnel == sorted(funnel, reverse=True) and funnel[0] == 300
    assert sum(d["sessions"] for d in allr["daily"]) == 300
    short = client.get("/stats", params={"days": 3}, headers=h).json()
    assert short["totals"]["sessions"] < 300
    assert client.get("/stats", params={"devices": "tv"}, headers=h).status_code == 422
    assert client.get("/stats", params={"date_from": "2030-01-02", "date_to": "2030-01-01"}, headers=h).status_code == 422
    future = client.get("/stats", params={"date_from": "2031-01-01", "date_to": "2031-02-01"}, headers=h).json()
    assert future["totals"]["sessions"] == 0


def test_summary_uses_selected_data(client, tokens):
    h = tokens["analyst"]
    r = client.post("/summary", json={"days": 30, "devices": ["mobile"], "sections": ["overview"], "question": "Vì sao thấp?"}, headers=h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["source"] == "rule" and set(d["data_used"]) == {"filters", "totals"}
    assert d["data_used"]["filters"]["devices"] == ["mobile"]
    assert "ANTHROPIC_API_KEY" in d["content"]
    assert client.post("/summary", json={"sections": []}, headers=h).status_code == 422
    empty = client.post("/summary", json={"date_from": "2031-01-01", "date_to": "2031-01-02"}, headers=h)
    assert empty.status_code == 422
    hist = client.get("/summaries", headers=tokens["viewer"]).json()
    assert hist[0]["author"] == "analyst@demo.com" and hist[0]["params"]["sections"] == ["overview"]


def test_post_event(client, tokens):
    r = client.post("/events", json={"visitor_id": "v1", "event_type": "purchase", "device": "mobile"}, headers=tokens["analyst"])
    assert r.status_code == 201
    assert client.post("/events", json={"visitor_id": "v1", "event_type": "bad"}, headers=tokens["analyst"]).status_code == 422
    assert client.post("/events", json={"visitor_id": "v1", "event_type": "click"}, headers=tokens["viewer"]).status_code == 403


def test_user_admin(client, tokens):
    users = client.get("/users", headers=tokens["admin"]).json()
    admin = next(u for u in users if u["email"] == "admin@demo.com")
    viewer = next(u for u in users if u["email"] == "viewer@demo.com")
    assert client.patch(f"/users/{admin['id']}", json={"role": "viewer"}, headers=tokens["admin"]).status_code == 400
    assert client.patch(f"/users/{admin['id']}", json={"is_active": False}, headers=tokens["admin"]).status_code == 400
    assert client.patch(f"/users/{viewer['id']}", json={"role": "analyst"}, headers=tokens["admin"]).json()["role"] == "analyst"
    # token cũ vẫn mang role cũ trong JWT nhưng quyền thật lấy từ DB
    assert client.post("/summary", json={"days": 30}, headers=tokens["viewer"]).status_code == 200
    client.patch(f"/users/{viewer['id']}", json={"role": "viewer"}, headers=tokens["admin"])
    assert client.post("/summary", json={"days": 30}, headers=tokens["viewer"]).status_code == 403
    # khóa tài khoản → token hết hiệu lực ngay
    client.patch(f"/users/{viewer['id']}", json={"is_active": False}, headers=tokens["admin"])
    assert client.get("/stats", headers=tokens["viewer"]).status_code == 401
    assert client.post("/auth/login", json={"email": "viewer@demo.com", "password": "viewer123"}).status_code == 403
    client.patch(f"/users/{viewer['id']}", json={"is_active": True}, headers=tokens["admin"])


def test_clear_data(client, tokens):
    r = client.delete("/data", headers=tokens["admin"])
    assert r.status_code == 200 and r.json()["sessions"] == 0 and r.json()["events"] == 0


def test_generated_data_fits_dashboard_window(client, tokens):
    """Tạo dữ liệu 'N ngày' thì bộ lọc 'N ngày' (hôm nay-N+1 → hôm nay) phải thấy đủ."""
    from datetime import datetime, timedelta
    client.post("/data/generate", json={"n_users": 20, "n_sessions": 200, "n_events": 500, "days": 14, "replace": True}, headers=tokens["admin"])
    today = datetime.utcnow().date()
    r = client.get("/stats", params={"date_from": (today - timedelta(days=13)).isoformat(), "date_to": today.isoformat()},
                   headers=tokens["viewer"]).json()
    assert r["totals"]["sessions"] == 200 and r["totals"]["events"] == 500
    one = client.post("/data/generate", json={"n_users": 3, "n_sessions": 30, "n_events": 60, "days": 1, "replace": True}, headers=tokens["admin"])
    assert one.status_code == 200
