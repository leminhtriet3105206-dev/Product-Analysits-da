from sqlalchemy import inspect, text

# Cột mới thêm vào bảng đã tồn tại (create_all không tự thêm cột).
NEW_COLUMNS = {"ai_summaries": {"user_id": "INTEGER", "params": "TEXT", "question": "TEXT"}}


def ensure_columns(engine) -> None:
    insp = inspect(engine)
    for table, cols in NEW_COLUMNS.items():
        if not insp.has_table(table):
            continue
        existing = {c["name"] for c in insp.get_columns(table)}
        with engine.begin() as conn:
            for name, typ in cols.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {typ}"))
