import os
import time

import httpx

LABELS = {"page_view": "Truy cập", "view_product": "Xem sản phẩm", "add_to_cart": "Thêm giỏ hàng", "purchase": "Thanh toán"}
DEVICE_VI = {"mobile": "di động", "desktop": "máy tính", "tablet": "máy tính bảng"}


def select_data(stats: dict, sections: list[str]) -> dict:
    """Chỉ giữ phần số liệu mà người dùng đã chọn gửi cho AI."""
    out = {"filters": stats["filters"]}
    if "overview" in sections:
        out["totals"] = stats["totals"]
    if "funnel" in sections:
        out["funnel"] = stats["funnel"]
        out["event_counts"] = stats["event_counts"]
    if "daily" in sections:
        out["daily"] = stats["daily"]
    if "devices" in sections:
        out["devices"] = stats["devices"]
    return out


def rule_based_summary(stats: dict, sections: list[str], question: str | None) -> str:
    """Tóm tắt theo luật: luôn chạy được, không cần API key. Chỉ nói về phần dữ liệu đã chọn."""
    t = stats["totals"]
    if not t["sessions"]:
        return "Dữ liệu được chọn không có phiên nào. Hãy mở rộng khoảng thời gian hoặc chọn thêm thiết bị."
    f = stats["filters"]
    lines = []
    if "overview" in sections:
        lines.append(
            f"Từ {f['since']} có {t['visitors']} người dùng, {t['sessions']} phiên, {t['events']} sự kiện "
            f"(trung bình {t['events_per_session']} sự kiện/phiên), tỷ lệ thoát {t['bounce_rate']}%.")
    if "funnel" in sections:
        fn = stats["funnel"]
        worst, worst_drop = None, 0.0
        for a, b in zip(fn, fn[1:]):
            if a["sessions"]:
                drop = 1 - b["sessions"] / a["sessions"]
                if drop > worst_drop:
                    worst, worst_drop = (a, b), drop
        if worst:
            lines.append(f"Người dùng rời đi nhiều nhất ở bước {LABELS[worst[0]['step']]} → "
                         f"{LABELS[worst[1]['step']]} (mất {worst_drop * 100:.0f}%).")
        if fn[0]["sessions"]:
            lines.append(f"Tỷ lệ chuyển đổi toàn phễu: {fn[-1]['sessions'] / fn[0]['sessions'] * 100:.1f}%.")
    if "daily" in sections and len(stats["daily"]) >= 4:
        d = stats["daily"]
        peak = max(d, key=lambda x: x["sessions"])
        half = len(d) // 2
        first = sum(x["sessions"] for x in d[:half]) / half
        second = sum(x["sessions"] for x in d[half:]) / (len(d) - half)
        if first:
            ch = (second / first - 1) * 100
            trend = "tăng" if ch > 5 else "giảm" if ch < -5 else "ổn định"
            lines.append(f"Lượng phiên {trend} ({ch:+.0f}% giữa nửa sau và nửa đầu); cao nhất ngày {peak['date']} ({peak['sessions']} phiên).")
    if "devices" in sections:
        devs = [d for d in stats["devices"] if d["sessions"] >= 5]
        if len(devs) >= 2:
            best = max(devs, key=lambda d: d["conversion_pct"])
            low = min(devs, key=lambda d: d["conversion_pct"])
            if best["device"] != low["device"]:
                lines.append(f"Thiết bị {DEVICE_VI[best['device']]} chuyển đổi tốt nhất ({best['conversion_pct']}%), "
                             f"{DEVICE_VI[low['device']]} thấp nhất ({low['conversion_pct']}%): nên xem lại trải nghiệm trên {DEVICE_VI[low['device']]}.")
    if not lines:
        lines.append("Chưa đủ dữ liệu trong phần đã chọn để rút ra nhận xét.")
    if question:
        lines.append("(Bản tóm tắt theo luật không trả lời được câu hỏi tự do; hãy cấu hình ANTHROPIC_API_KEY hoặc GEMINI_API_KEY để AI trả lời.)")
    return " ".join(lines)


def _build_prompt(data: dict, question: str | None) -> str:
    prompt = ("Bạn là chuyên gia product analytics. Dựa trên số liệu JSON sau, viết bản tóm tắt hành vi người dùng "
              "bằng tiếng Việt, tối đa 6 câu: điểm đáng chú ý nhất, bước rơi rụng lớn nhất (nếu có số liệu phễu) "
              "và 1-2 gợi ý hành động. Chỉ dùng số liệu được cung cấp, không bịa thêm.\n")
    if question:
        prompt += f"Ngoài ra hãy trả lời câu hỏi của người dùng: {question}\n"
    return prompt + f"\nSố liệu: {data}"


def _call_claude(key: str, prompt: str) -> str:
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"), "max_tokens": 700,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=40)
    r.raise_for_status()
    return r.json()["content"][0]["text"].strip()


def _gemini_text(j: dict) -> str:
    texts = [c.get("text", "") for step in j.get("steps", []) if step.get("type") == "model_output"
             for c in step.get("content", []) if c.get("type") == "text"]
    if not texts and j.get("output_text"):
        texts = [j["output_text"]]
    if not texts:
        raise ValueError("phản hồi không có văn bản")
    return "\n".join(texts).strip()


RETRY_STATUS = {429, 500, 502, 503, 504} 


def _call_gemini(key: str, prompt: str) -> str:
    """Thử lại khi Google quá tải; GEMINI_MODEL có thể là danh sách cách nhau bởi dấu phẩy để dự phòng."""
    models = [m.strip() for m in os.getenv("GEMINI_MODEL", "gemini-3.8-flash").split(",") if m.strip()]
    last = None
    for model in models:
        for attempt in range(3):
            last = httpx.post(
                "https://generativelanguage.googleapis.com/v1beta/interactions",
                headers={"x-goog-api-key": key, "content-type": "application/json"},
                json={"model": model, "input": prompt}, timeout=40)
            if last.status_code in RETRY_STATUS:
                time.sleep(2 ** attempt)  # chờ 1s, 2s, 4s rồi thử lại
                continue
            last.raise_for_status()
            return _gemini_text(last.json())
    last.raise_for_status()
    raise RuntimeError("Gemini không phản hồi")


def pick_provider() -> tuple[str | None, str | None]:
    """AI_PROVIDER = auto (Claude nếu có key, không thì Gemini) | claude | gemini."""
    claude, gemini = os.getenv("ANTHROPIC_API_KEY"), os.getenv("GEMINI_API_KEY")
    mode = os.getenv("AI_PROVIDER", "auto").lower()
    if mode == "claude":
        return ("claude", claude) if claude else (None, None)
    if mode == "gemini":
        return ("gemini", gemini) if gemini else (None, None)
    if claude:
        return "claude", claude
    if gemini:
        return "gemini", gemini
    return None, None


def ai_summary(data: dict, question: str | None) -> tuple[str | None, str | None, str | None]:
    """Trả (nội dung, lỗi, nhà cung cấp). Không có key hoặc lỗi thì nội dung = None để dùng bản theo luật."""
    provider, key = pick_provider()
    if not provider:
        return None, None, None
    try:
        call = _call_claude if provider == "claude" else _call_gemini
        return call(key, _build_prompt(data, question)), None, provider
    except Exception as e:
        return None, f"Không gọi được {provider.capitalize()} ({type(e).__name__}: {str(e)[:120]})", provider